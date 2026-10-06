"""MQTT delivery path and alert publishing (DESIGN D12, UPV Idea #1). Optional: inactive
unless MQTT_HOST is set.

The explorer subscribes to the Messages API's block topic with a persistent session
(fixed client id, clean_session=False, QoS 1, manual acknowledgement): the broker keeps messages
for the explorer while it is down, and a message is acknowledged only after it is stored.
Records go through the same idempotent store() as POST /api/ingest.
"""
import json
import logging
import os
import time

import paho.mqtt.client as mqtt
from pydantic import ValidationError

MQTT_HOST = os.getenv("MQTT_HOST", "")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
BLOCKS_TOPIC = os.getenv("MQTT_BLOCKS_TOPIC", "aerios/iota/blocks")
ALERTS_TOPIC = os.getenv("MQTT_ALERTS_TOPIC", "aerios/explorer/alerts")
CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "advanced-explorer")
# Retry a failed store (e.g. database restarting) before giving up on this delivery. The total
# (~45 s) stays well inside the broker's 1.5 x 60 s keepalive grace while paho's thread is busy.
STORE_RETRY_DELAYS = (1, 2, 4, 8, 15, 15)
log = logging.getLogger("explorer.mqtt")
_client: mqtt.Client | None = None


def handle_message(payload: bytes, store, model) -> dict | None:
    """Validate one block record from MQTT and store it. Invalid records are logged and dropped."""
    try:
        item = model.model_validate_json(payload)
    except ValidationError as e:
        log.warning("ignored invalid MQTT record: %s", e.errors()[:1])
        return None
    return store(item, via="mqtt")


def deliver(client, msg, store, model) -> bool:
    """Store one MQTT message and acknowledge it only once it is stored (or is invalid and can
    never be stored). If storing keeps failing, the message stays unacknowledged and the broker
    redelivers it on the next reconnect of this persistent session. Returns True if acked."""
    for delay in (*STORE_RETRY_DELAYS, None):
        try:
            r = handle_message(msg.payload, store, model)
        except Exception:
            log.exception("failed to store MQTT record (retry in %ss)", delay)
            if delay is None:
                log.error("leaving MQTT message %s unacknowledged; the broker redelivers it on reconnect", msg.mid)
                return False
            time.sleep(delay)
            continue
        client.ack(msg.mid, msg.qos)
        if r:
            log.info("MQTT record %s created=%s", r["block_id"][:18], r["created"])
        return True
    return False


def start(store, model) -> mqtt.Client | None:
    global _client
    if not MQTT_HOST:
        return None
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=CLIENT_ID, clean_session=False,
                    manual_ack=True)

    def on_connect(client, userdata, connect_flags, reason_code, properties):
        log.info("connected to MQTT %s:%s (%s); subscribing to %s", MQTT_HOST, MQTT_PORT, reason_code, BLOCKS_TOPIC)
        client.subscribe(BLOCKS_TOPIC, qos=1)

    def on_message(client, userdata, msg):
        try:                                      # an exception here would stop paho's network thread
            deliver(client, msg, store, model)
        except Exception:
            log.exception("unexpected error delivering MQTT message")

    c.on_connect, c.on_message = on_connect, on_message
    c.reconnect_delay_set(1, 30)
    c.connect_async(MQTT_HOST, MQTT_PORT)
    c.loop_start()
    _client = c
    return c


def stop() -> None:
    if _client:
        _client.loop_stop()
        _client.disconnect()


def publish_alert(payload: dict) -> None:
    """Best effort: never raises."""
    if _client is None:
        return
    try:
        info = _client.publish(ALERTS_TOPIC, json.dumps(payload), qos=1)
        if info.rc != mqtt.MQTT_ERR_SUCCESS:
            log.warning("alert %s not published to MQTT now (rc=%s)", payload.get("id"), info.rc)
    except (ValueError, OSError) as e:
        log.warning("alert %s MQTT publish failed: %s", payload.get("id"), e)
