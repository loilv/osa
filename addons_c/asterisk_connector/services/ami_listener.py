#!/usr/bin/env python3
"""
Asterisk AMI Listener Service
=============================
Standalone service that connects to Asterisk AMI via panoramisk,
listens for call events, and forwards them to Odoo's HTTP endpoint.

Usage:
    python ami_listener.py

Requires:
    pip install panoramisk requests python-dotenv
"""

import os
import json
import logging
import asyncio
import requests
from panoramisk import Manager
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

ODOO_URL = os.getenv('ODOO_URL', 'http://localhost:8069')
ODOO_API_KEY = os.getenv('ODOO_API_KEY', '')

# Events to capture and forward to Odoo
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


# ====================== Event Handler ======================

def forward_to_odoo(event_name, event_data):
    """Forward AMI event to Odoo via HTTP POST"""
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
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
        if resp.status_code == 200:
            _logger.debug('Event %s forwarded successfully', event_name)
        else:
            _logger.warning('Event %s forward failed: %s %s',
                            event_name, resp.status_code, resp.text[:200])
    except requests.RequestException as e:
        _logger.error('Failed to forward event %s to Odoo: %s', event_name, e)


@manager.register_event('*')
async def ami_callback(mngr, msg):
    """Handle all AMI events, filter and forward relevant ones"""
    if msg.Event not in TRACKED_EVENTS:
        return

    # Convert message to dict
    event_data = {}
    for key, val in msg.items():
        event_data[key] = val

    # For Newexten: only track MixMonitor (recording start)
    if msg.Event == 'Newexten':
        if event_data.get('Application') != 'MixMonitor':
            return
        _logger.info('Recording started: %s', event_data.get('AppData', ''))

    _logger.info('AMI Event: %s | UniqueID: %s | Channel: %s',
                 msg.Event,
                 event_data.get('Uniqueid', ''),
                 event_data.get('Channel', ''))

    # Forward to Odoo in a thread to avoid blocking the event loop
    loop = asyncio.get_event_loop()
    loop.run_in_executor(None, forward_to_odoo, msg.Event, event_data)


# ====================== Main ======================

if __name__ == '__main__':
    _logger.info('Starting AMI Listener...')
    _logger.info('AMI: %s:%s (user: %s)', AMI_HOST, AMI_PORT, AMI_USERNAME)
    _logger.info('Odoo: %s', ODOO_URL)

    manager.on_connect = on_connect
    manager.on_login = on_login
    manager.on_disconnect = on_disconnect
    manager.connect(run_forever=True, on_startup=on_startup, on_shutdown=on_shutdown)
