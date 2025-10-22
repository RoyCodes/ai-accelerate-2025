import json
import os
import time
from typing import Dict, Any, List

import paho.mqtt.client as mqtt
from fivetran_connector_sdk import Connector
from fivetran_connector_sdk import Logging as log
from fivetran_connector_sdk import Operations as op

ENV_MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
ENV_MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
ENV_MQTT_USER = os.getenv("MQTT_USER", "")
ENV_MQTT_PASS = os.getenv("MQTT_PASS", "")
ENV_TOPIC     = os.getenv("TOPIC", "factory/+/telemetry")
ENV_QOS       = int(os.getenv("QOS", "1"))
ENV_BATCH_S   = float(os.getenv("BATCH_SECONDS", "10"))
ENV_BATCH_MAX = int(os.getenv("BATCH_MAX", "1000"))
ENV_TABLE     = os.getenv("TABLE_NAME", "telemetry")

def update(configuration: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
    """Collect a short MQTT batch and upsert to destination via Fivetran."""

    def get_cfg(name: str, cast, default):
        """Prefer configuration[name], then env var, else default; always cast safely."""
        v = configuration.get(name, None)
        if v is None:
            v = os.getenv(name, None)
        if v is None or (isinstance(v, str) and v.strip() == ""):
            return default
        try:
            return cast(v)
        except Exception:
            return default

    mqtt_host: str = get_cfg("MQTT_HOST", str, ENV_MQTT_HOST)
    mqtt_port: int = get_cfg("MQTT_PORT", int, ENV_MQTT_PORT)
    mqtt_user: str = get_cfg("MQTT_USER", str, ENV_MQTT_USER)
    mqtt_pass: str = get_cfg("MQTT_PASS", str, ENV_MQTT_PASS)
    topic:     str = get_cfg("TOPIC", str, ENV_TOPIC)
    qos:       int = get_cfg("QOS", int, ENV_QOS)
    batch_s: float = get_cfg("BATCH_SECONDS", float, ENV_BATCH_S)
    batch_max: int = get_cfg("BATCH_MAX", int, ENV_BATCH_MAX)
    table:    str  = get_cfg("TABLE_NAME", str, ENV_TABLE)

    log.fine(f"MQTT batch start host={mqtt_host} port={mqtt_port} topic={topic} qos={qos}")

    collected: List[Dict[str, Any]] = []
    last_ts_seen: float = float(state.get("last_ts", 0.0))  # always a float

    def on_connect(client, userdata, flags, rc, *args):
        if rc == 0:
            log.fine("Connected to MQTT broker. Subscribing…")
            client.subscribe(topic, qos=qos)
        else:
            log.warning(f"MQTT connect failed rc={rc}")

    def on_message(client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            if not isinstance(payload, dict):
                return
            ts = payload.get("ts")
            if isinstance(ts, (int, float)) and float(ts) <= last_ts_seen:
                return
            collected.append(payload)
        except Exception as e:
            log.warning(f"Bad payload on {msg.topic}: {e}; skipping")

    client = mqtt.Client()
    if mqtt_user:
        client.username_pw_set(mqtt_user, mqtt_pass)
    client.on_connect = on_connect
    client.on_message = on_message

    try:
        client.connect(mqtt_host, mqtt_port, keepalive=30)
        client.loop_start()

        start = time.monotonic()
        while (time.monotonic() - start) < batch_s and len(collected) < batch_max:
            time.sleep(0.1)

    except Exception as e:
        log.warning(f"MQTT operation failed: {e}")

    finally:
        with _suppress():
            client.loop_stop()
        with _suppress():
            client.disconnect()

    if collected:
        log.fine(f"Collected {len(collected)} messages → writing to '{table}'")
        max_ts = last_ts_seen
        for record in collected:
            op.upsert(table=table, data=record)
            ts = record.get("ts")
            if isinstance(ts, (int, float)):
                fts = float(ts)
                if fts > max_ts:
                    max_ts = fts
        state["last_ts"] = float(max_ts)

    op.checkpoint(state)
    return state

class _suppress:
    def __enter__(self): return self
    def __exit__(self, *args): return True

connector = Connector(update=update)

if __name__ == "__main__":
    connector.debug()
