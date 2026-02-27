#!/usr/bin/env python3
"""
Asterisk AMI Listener → Kafka Producer
=======================================
Connects to Asterisk AMI via panoramisk, captures call events,
and publishes them to a Kafka topic for downstream processing.

Architecture:
    AMI → ami_listener.py (Kafka producer) → Kafka topic
    Kafka topic → kafka_consumer.py → Odoo /asterisk/events

Usage:
    python ami_listener.py
"""

import os
import json
import logging
import asyncio
from panoramisk import Manager
from kafka import KafkaProducer
from kafka.errors import KafkaError, NoBrokersAvailable
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
_logger = logging.getLogger('ami_listener')

# ====================== Configuration ======================

AMI_HOST = os.getenv('AMI_HOST', '127.0.0.1')
AMI_PORT = int(os.getenv('AMI_PORT', 5038))
AMI_USERNAME = os.getenv('AMI_USERNAME', 'admin')
AMI_SECRET = os.getenv('AMI_SECRET', 'admin123')

KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'asterisk_ami_events')

# Events to capture and publish
TRACKED_EVENTS = {
    'Newchannel',
    'Dial',
    'Ringing',
    'Answer',
    'Hangup',
    'Cdr',
    'Newexten',
    'Transfer',
    'BridgeEnter',
    'DialState',
}

# ====================== Kafka Producer ======================

_producer = None


def get_producer():
    """Lazy-init Kafka producer với retry"""
    global _producer
    if _producer is not None:
        return _producer

    try:
        _producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP.split(','),
            value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            acks='all',
            retries=5,
            retry_backoff_ms=500,
            max_block_ms=10000,
            linger_ms=5,
            compression_type='gzip',
        )
        _logger.info('Kafka producer connected: %s', KAFKA_BOOTSTRAP)
        return _producer
    except NoBrokersAvailable:
        _logger.error('No Kafka brokers available at %s', KAFKA_BOOTSTRAP)
        return None
    except KafkaError as e:
        _logger.error('Kafka producer init error: %s', e)
        return None


# ====================== AMI Manager ======================

manager = Manager(
    host=AMI_HOST,
    port=AMI_PORT,
    username=AMI_USERNAME,
    secret=AMI_SECRET,
    ping_delay=10,
    ping_interval=10,
    reconnect_timeout=2,
)


def on_connect(mngr):
    _logger.info('Connected to AMI %s:%s', mngr.config['host'], mngr.config['port'])


def on_login(mngr):
    _logger.info('Logged in as %s to AMI %s:%s',
                 mngr.config['username'], mngr.config['host'], mngr.config['port'])


def on_disconnect(mngr, exc):
    _logger.warning('Disconnected from AMI %s:%s: %s',
                    mngr.config['host'], mngr.config['port'], exc)


async def on_startup(mngr):
    await asyncio.sleep(0.1)
    _logger.info('AMI listener started')


async def on_shutdown(mngr):
    await asyncio.sleep(0.1)
    _logger.info('AMI listener shutdown')
    if _producer:
        _producer.flush(timeout=5)
        _producer.close(timeout=5)


# ====================== Event Handler ======================

def publish_to_kafka(event_name, event_data):
    """Publish AMI event to Kafka topic.
    Partition key = Uniqueid để đảm bảo thứ tự event cho cùng cuộc gọi.
    """
    producer = get_producer()
    if not producer:
        _logger.error('Kafka producer not available — dropping event %s', event_name)
        return

    message = {
        'event': event_name,
        'data': event_data,
    }

    # Dùng Uniqueid làm partition key → cùng cuộc gọi luôn vào cùng partition → đảm bảo thứ tự
    partition_key = event_data.get('Uniqueid') or event_data.get('Linkedid') or ''

    try:
        future = producer.send(KAFKA_TOPIC, value=message, key=partition_key)
        # Non-blocking: log error via callback
        future.add_errback(
            lambda exc: _logger.error('Kafka send failed for %s: %s', event_name, exc)
        )
        _logger.debug('Event %s published to Kafka (key=%s)', event_name, partition_key)
    except KafkaError as e:
        _logger.error('Failed to publish event %s to Kafka: %s', event_name, e)
        # Reset producer to reconnect on next call
        global _producer
        _producer = None


@manager.register_event('*')
async def ami_callback(mngr, msg):
    """Handle all AMI events, filter and publish to Kafka"""
    if msg.Event not in TRACKED_EVENTS:
        return

    # Convert message to dict
    event_data = {}
    for key, val in msg.items():
        event_data[key] = val

    # Newexten: chỉ track MixMonitor (recording start)
    if msg.Event == 'Newexten':
        if event_data.get('Application') != 'MixMonitor':
            return
        _logger.info('Recording started: %s', event_data.get('AppData', ''))

    _logger.info('AMI Event: %s | UniqueID: %s | Channel: %s',
                 msg.Event,
                 event_data.get('Uniqueid', ''),
                 event_data.get('Channel', ''))

    # Publish to Kafka in a thread to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, publish_to_kafka, msg.Event, event_data)


# ====================== Main ======================

def check_kafka_connection():
    """Kiểm tra kết nối tới Kafka khi khởi động"""
    producer = get_producer()
    if producer:
        _logger.info('Kafka connection OK: %s (topic: %s)', KAFKA_BOOTSTRAP, KAFKA_TOPIC)
        return True
    return False


if __name__ == '__main__':
    _logger.info('Starting AMI Listener (Kafka mode)...')
    _logger.info('AMI: %s:%s (user: %s)', AMI_HOST, AMI_PORT, AMI_USERNAME)
    _logger.info('Kafka: %s (topic: %s)', KAFKA_BOOTSTRAP, KAFKA_TOPIC)

    if not check_kafka_connection():
        _logger.error('Cannot connect to Kafka — events will be lost!')

    manager.on_connect = on_connect
    manager.on_login = on_login
    manager.on_disconnect = on_disconnect
    manager.connect(run_forever=True, on_startup=on_startup, on_shutdown=on_shutdown)
