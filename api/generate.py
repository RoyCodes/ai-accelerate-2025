import os, time, json, asyncio
from amqtt.broker import Broker
from amqtt.client import MQTTClient
from amqtt.mqtt.constants import QOS_0

MQTT_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
TOPIC      = os.getenv("TOPIC", "factory/demo/hello")
PERIOD_SEC = float(os.getenv("PERIOD_SEC", "2.0"))

BROKER_CFG = {
    "listeners": {"default": {"type": "tcp", "bind": f"{MQTT_HOST}:{MQTT_PORT}"}},
    "sys_interval": 10,
    "topic_check": {"enabled": False},
}

async def start_broker():
    broker = Broker(BROKER_CFG)
    try:
        await broker.start()
        print(f"[broker] listening on {MQTT_HOST}:{MQTT_PORT}", flush=True)
        return broker
    except Exception as e:
        # If the port is already in use, assume a broker is already running.
        print(f"[broker] start skipped ({e}); will publish to existing broker.", flush=True)
        return None

async def publish_loop():
    url = f"mqtt://{MQTT_HOST}:{MQTT_PORT}/"
    client = MQTTClient(client_id="generator")
    await client.connect(url)
    print(f"[publisher] connected to {url}", flush=True)

    seq = 0
    try:
        while True:
            seq += 1
            payload = {"msg": "hello world", "seq": seq, "ts": time.time()}
            await client.publish(TOPIC, json.dumps(payload).encode(), qos=QOS_0)
            print(f"[publisher] -> {TOPIC} #{seq}", flush=True)
            await asyncio.sleep(PERIOD_SEC)
    finally:
        await client.disconnect()
        print("[publisher] disconnected", flush=True)

async def main():
    broker = await start_broker()
    try:
        await publish_loop()  # runs forever until process is stopped
    finally:
        if broker is not None:
            await broker.shutdown()
            print("[broker] shutdown", flush=True)

if __name__ == "__main__":
    asyncio.run(main())