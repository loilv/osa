#!/usr/bin/env python3
"""
Kafka Consumer → Odoo HTTP Forwarder
=====================================
Consumes AMI events from Kafka topic and forwards them
to Odoo's /asterisk/events HTTP endpoint.

Architecture:
    AMI → ami_listener.py (Kafka producer) → Kafka topic
    Kafka topic → kafka_consumer.py (this) → Odoo /asterisk/events

Usage:
    python kafka_consumer.py
"""

import os
import json
import logging
import signal
import sys
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from kafka import KafkaConsumer
from kafka.errors import KafkaError, NoBrokersAvailable
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
_logger = logging.getLogger('kafka_consumer')

# ====================== Configuration ======================

KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'asterisk_ami_events')
KAFKA_GROUP_ID = os.getenv('KAFKA_GROUP_ID', 'asterisk_odoo_consumer')

ODOO_URL = os.getenv('ODOO_URL', 'http://localhost:8019')
ODOO_API_KEY = os.getenv('ODOO_API_KEY', '')
MAX_RETRIES = int(os.getenv('MAX_RETRIES', 3))

# ====================== HTTP Session with retry ======================

_session = requests.Session()
_retry_strategy = Retry(
    total=MAX_RETRIES,
    backoff_factor=0.5,
    status_forcelist=[502, 503, 504],
    allowed_methods=['POST'],
)
_adapter = HTTPAdapter(
    max_retries=_retry_strategy,
    pool_connections=5,
    pool_maxsize=10,
)
_session.mount('http://', _adapter)
_session.mount('https://', _adapter)

# ====================== Graceful shutdown ======================

_running = True


def _signal_handler(signum, frame):
    global _running
    _logger.info('Received signal %s — shutting down...', signum)
    _running = False


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ====================== Odoo Forwarder ======================

def forward_to_odoo(event_name, event_data):
    """Forward event to Odoo /asterisk/events endpoint (with auto-retry)"""
    url = f"{ODOO_URL}/asterisk/events"
    payload = {
        'event': event_name,
        'data': event_data,
    }
    headers = {
        'Content-Type': 'application/json',
    }
    if ODOO_API_KEY:
        headers['X-Api-Key'] = ODOO_API_KEY

    try:
        resp = _session.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            _logger.debug('Event %s forwarded OK to Odoo', event_name)
            return True
        else:
            _logger.warning('Event %s forward failed [%s]: %s',
                            event_name, resp.status_code, resp.text[:500])
            return False
    except requests.ConnectionError as e:
        _logger.error('Cannot connect to Odoo (%s) for event %s: %s', ODOO_URL, event_name, e)
        return False
    except requests.RequestException as e:
        _logger.error('Failed to forward event %s to Odoo: %s', event_name, e)
        return False


def check_odoo_connection():
    """Kiểm tra kết nối tới Odoo khi khởi động"""
    url = f"{ODOO_URL}/web/webclient/version_info"
    try:
        resp = _session.get(url, timeout=5)
        if resp.status_code == 200:
            _logger.info('Odoo connection OK: %s', ODOO_URL)
            return True
        else:
            _logger.warning('Odoo responded with status %s (still reachable)', resp.status_code)
            return True
    except requests.ConnectionError:
        _logger.error('Cannot connect to Odoo at %s', ODOO_URL)
        return False
    except Exception as e:
        _logger.error('Odoo connection check failed: %s', e)
        return False


# ====================== Main Consumer Loop ======================

def run_consumer():
    """Main consumer loop — đọc events từ Kafka và forward tới Odoo"""
    _logger.info('Connecting to Kafka: %s (topic: %s, group: %s)',
                 KAFKA_BOOTSTRAP, KAFKA_TOPIC, KAFKA_GROUP_ID)

    try:
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP.split(','),
            group_id=KAFKA_GROUP_ID,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
            auto_offset_reset='earliest',
            enable_auto_commit=True,
            auto_commit_interval_ms=5000,
            max_poll_records=50,
            session_timeout_ms=30000,
            heartbeat_interval_ms=10000,
        )
    except NoBrokersAvailable:
        _logger.error('No Kafka brokers available at %s', KAFKA_BOOTSTRAP)
        sys.exit(1)
    except KafkaError as e:
        _logger.error('Kafka consumer error: %s', e)
        sys.exit(1)

    _logger.info('Kafka consumer started — waiting for events...')

    try:
        while _running:
            # Poll with timeout để có thể check _running flag
            records = consumer.poll(timeout_ms=1000)

            for topic_partition, messages in records.items():
                for msg in messages:
                    try:
                        payload = msg.value
                        event_name = payload.get('event', '')
                        event_data = payload.get('data', {})

                        _logger.info('Kafka msg [offset=%s] Event: %s | UniqueID: %s | Channel: %s',
                                     msg.offset, event_name,
                                     event_data.get('Uniqueid', ''),
                                     event_data.get('Channel', ''))

                        forward_to_odoo(event_name, event_data)

                    except Exception as e:
                        _logger.error('Error processing Kafka message at offset %s: %s',
                                      msg.offset, e, exc_info=True)

    except KeyboardInterrupt:
        _logger.info('Consumer interrupted')
    finally:
        consumer.close()
        _logger.info('Kafka consumer closed')


if __name__ == '__main__':
    _logger.info('Starting Kafka Consumer...')
    _logger.info('Kafka: %s (topic: %s, group: %s)', KAFKA_BOOTSTRAP, KAFKA_TOPIC, KAFKA_GROUP_ID)
    _logger.info('Odoo: %s', ODOO_URL)

    if not check_odoo_connection():
        _logger.warning('Odoo is not reachable — will retry on each message')

    run_consumer()
