#!/usr/bin/env bash
set -euo pipefail

# Load env if present
if [ -f "$(dirname "$0")/.env" ]; then
  # shellcheck disable=SC1091
  source "$(dirname "$0")/.env"
fi

# ENV fallbacks
PROJECT_ID="${PROJECT_ID:-your-gcp-project}"
REGION="${REGION:-us-west1}"
ZONE="${ZONE:-us-west1-b}"
VM_NAME="${VM_NAME:-mqtt-factory}"

gcloud config set project "$PROJECT_ID" >/dev/null
gcloud config set compute/region "$REGION" >/dev/null
gcloud config set compute/zone "$ZONE" >/dev/null

# 1) Firewall
gcloud compute firewall-rules create allow-mqtt-1883 \
  --allow=tcp:1883 --direction=INGRESS --target-tags=mqtt --priority=1000 \
  --description="Allow MQTT on 1883" || true

gcloud compute instances create "$VM_NAME" \
  --zone "$ZONE" \
  --machine-type=e2-micro \
  --image-family=debian-12 --image-project=debian-cloud \
  --tags=mqtt \
  --metadata-from-file startup-script=vm/startup.sh

# 3) Print broker IP
BROKER_IP=$(gcloud compute instances describe "$VM_NAME" --zone "$ZONE" \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)')
echo "BROKER_IP=$BROKER_IP"
echo "Tip: test with →  mosquitto_sub -h $BROKER_IP -u demo -P demo123 -t 'factory/#' -v"