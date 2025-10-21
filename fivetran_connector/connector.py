import json
import os
import time
import paho.mqtt.client as mqtt

from fivetran_connector_sdk import Connector
from fivetran_connector_sdk import Logging as log
from fivetran_connector_sdk import Operations as op

# --- Configuration ---
MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC     = os.getenv("TOPIC", "factory/demo/hello")

# Collect for either this many seconds or until we hit this many messages
BATCH_SECONDS = float(os.getenv("BATCH_SECONDS", "10"))
BATCH_MAX     = int(os.getenv("BATCH_MAX", "500"))


def update(configuration: dict, state: dict) -> dict:
    """
    Connect to MQTT, collect a short batch of JSON messages from TOPIC,
    write them via op.upsert(table="hello_messages"), checkpoint, and return.
    """
    log.fine(f"Starting MQTT batch: host={MQTT_HOST} port={MQTT_PORT} topic={TOPIC}")
    collected: list[dict] = []

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            log.fine("Connected to MQTT broker. Subscribing…")
            client.subscribe(TOPIC, qos=1)
        else:
            log.warning(f"MQTT connect failed rc={rc}")

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            # Ensure dict shape for op.upsert; ignore non-dict payloads
            if isinstance(payload, dict):
                collected.append(payload)
            else:
                log.warning("Skipping non-dict JSON payload")
        except Exception as e:
            log.warning(f"Bad payload on {msg.topic}: {e}; skipping")

    client = mqtt.Client()
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
        client.loop_start()

        start = time.monotonic()
        while (time.monotonic() - start) < BATCH_SECONDS and len(collected) < BATCH_MAX:
            time.sleep(0.1)

    except Exception as e:
        log.warning(f"MQTT operation failed: {e}")

    finally:
        try:
            client.loop_stop()
        except Exception:
            pass
        try:
            client.disconnect()
        except Exception:
            pass

    if collected:
        log.fine(f"Collected {len(collected)} messages → writing to table 'hello_messages'")
        for record in collected:
            # Upsert one row at a time; Fivetran will infer schema.
            # If you add a stable natural key (e.g., record['machine_id'] + ts),
            # pass it as part of 'data' so replays dedupe naturally.
            op.upsert(table="hello_messages", data=record)

    # Persist any lightweight progress (optional for this POC)
    op.checkpoint(state)
    return state


connector = Connector(update=update)

if __name__ == "__main__":
    connector.debug()