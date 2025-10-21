#!/bin/bash
set -e

# --- OS packages ---
apt-get update
apt-get install -y mosquitto mosquitto-clients python3 python3-venv

# --- Mosquitto: single-file config (avoid conf.d duplicates) ---
cp /etc/mosquitto/mosquitto.conf /etc/mosquitto/mosquitto.conf.bak || true
cat >/etc/mosquitto/mosquitto.conf <<'EOF'
listener 1883 0.0.0.0
allow_anonymous false
password_file /etc/mosquitto/passwd

persistence true
persistence_location /var/lib/mosquitto/

log_dest syslog
log_dest file /var/log/mosquitto/mosquitto.log
EOF

# Auth + dirs
mosquitto_passwd -b -c /etc/mosquitto/passwd demo demo123
mkdir -p /var/log/mosquitto /var/lib/mosquitto
chown -R mosquitto:mosquitto /var/log/mosquitto /var/lib/mosquitto /etc/mosquitto/passwd
chmod 750 /var/log/mosquitto /var/lib/mosquitto
chmod 640 /etc/mosquitto/passwd

systemctl enable mosquitto
systemctl restart mosquitto

# --- Telemetry publisher ---
mkdir -p /opt/telemetry
python3 -m venv /opt/telemetry/venv
/opt/telemetry/venv/bin/pip install --no-input paho-mqtt

cat >/opt/telemetry/machines.json <<'EOF'
[
  {"machine_id":"mx-01","name":"Mixer 3000","type":"Mixer",
   "sensors":{"temp_c":[26,32],"speed_rpm":[800,1200],"vibration_g":[0.02,0.05],"motor_current_a":[4.0,8.0],"bowl_load_kg":[50,120]}},
  {"machine_id":"kn-02","name":"Kneader Pro","type":"Kneader",
   "sensors":{"dough_temp_c":[24,30],"torque_nm":[60,120],"motor_current_a":[5.0,9.0],"speed_rpm":[60,150]}},
  {"machine_id":"ct-03","name":"CookieCutter X","type":"Cutter",
   "sensors":{"blade_rpm":[800,1600],"blade_vibration_g":[0.01,0.03],"air_pressure_bar":[5.5,7.0],"piece_length_mm":[48,52]}},
  {"machine_id":"ov-04","name":"Tunnel Oven","type":"Oven",
   "sensors":{"zone1_temp_c":[185,200],"zone2_temp_c":[190,210],"humidity_pct":[5,12],"belt_speed_mpm":[3,6]}},
  {"machine_id":"cl-05","name":"Spiral Cooler","type":"Cooler",
   "sensors":{"air_temp_c":[18,24],"airflow_cfm":[500,800],"humidity_pct":[30,50],"belt_speed_mpm":[3,6]}},
  {"machine_id":"pk-06","name":"Flow Packer","type":"Packer",
   "sensors":{"seal_temp_c":[170,195],"seal_pressure_bar":[1.6,2.4],"conveyor_speed_mpm":[4,8],"reject_rate_pct":[0.0,1.5]}}
]
EOF

cat >/usr/local/bin/telemetry.py <<'EOF'
import json, os, time, random, uuid
from pathlib import Path
import paho.mqtt.client as mqtt

BROKER_HOST = os.getenv("MQTT_HOST", "127.0.0.1")
BROKER_PORT = int(os.getenv("MQTT_PORT", "1883"))
BROKER_USER = os.getenv("MQTT_USER", "demo")
BROKER_PASS = os.getenv("MQTT_PASS", "demo123")
TOPIC_BASE  = os.getenv("TOPIC_BASE", "factory")
INTERVAL_S  = float(os.getenv("INTERVAL_S", "1.0"))
QOS         = int(os.getenv("QOS", "1"))

machines = json.loads(Path("/opt/telemetry/machines.json").read_text())

def rand_in(lo, hi): return random.uniform(lo, hi)
def greener_factor_by_hour(h): return 0.9 if 0 <= h < 6 else 1.0 if 6 <= h < 18 else 0.95

def next_snapshot(m):
    sensors = {}
    for k, (lo, hi) in m["sensors"].items():
        base = rand_in(lo, hi)
        jitter = (hi - lo) * 0.01
        sensors[k] = round(base + random.uniform(-jitter, jitter), 4)
    power_w = round(800 + random.uniform(-80, 80) + sensors.get("motor_current_a", 6)*60, 1)
    hour = time.localtime().tm_hour
    co2_factor = 0.0000004 * greener_factor_by_hour(hour)
    co2_kg_per_min = round(power_w * co2_factor, 6)
    noise_db = int(78 + random.uniform(-3, 6))
    ambient_temp_c = int(24 + random.uniform(-1, 6))
    scrap_rate_pct = round(max(0.0, min(3.0, random.uniform(0, 1.5) + (sensors.get("temp_c", 28) - 30)*0.1)), 2)
    batch_id = f"B-{time.strftime('%Y%m%d')}-{hour:02d}"
    ts = time.time()
    pk = f"{m['machine_id']}:{int(ts*1000)}"
    return {"pk": pk, "ts": ts, "machine_id": m["machine_id"], "name": m["name"], "type": m["type"],
            **sensors, "power_w": power_w, "co2_kg_per_min": co2_kg_per_min,
            "noise_db": noise_db, "ambient_temp_c": ambient_temp_c,
            "scrap_rate_pct": scrap_rate_pct, "batch_id": batch_id}

def main():
    client = mqtt.Client(client_id=f"telemetry-pub-{uuid.uuid4().hex[:8]}")
    client.username_pw_set(BROKER_USER, BROKER_PASS)
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=30)
    client.loop_start()
    try:
        while True:
            for m in machines:
                payload = next_snapshot(m)
                topic = f"{TOPIC_BASE}/{m['machine_id']}/telemetry"
                client.publish(topic, json.dumps(payload), qos=QOS, retain=False)
            time.sleep(INTERVAL_S)
    finally:
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()
EOF
chmod +x /usr/local/bin/telemetry.py

cat >/etc/systemd/system/telemetry.service <<'EOF'
[Unit]
Description=Cookie Factory Telemetry Publisher
After=mosquitto.service
Wants=mosquitto.service

[Service]
Type=simple
Environment=MQTT_HOST=127.0.0.1
Environment=MQTT_PORT=1883
Environment=MQTT_USER=demo
Environment=MQTT_PASS=demo123
Environment=TOPIC_BASE=factory
Environment=INTERVAL_S=1.0
Environment=QOS=1
ExecStart=/opt/telemetry/venv/bin/python /usr/local/bin/telemetry.py
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable telemetry
systemctl restart telemetry
