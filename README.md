### Steps Taken:
1. `uv init`
2. added mesop and fastapi
3. set up fastapi main.py to load mesop front-end from /ui/home.py

### Technologies Used:
1. uv
2. fastAPI
3. Mesop
4. aMQTT


### MQTT VM Notes:
1. ensure you have Google SDK installed, are logged in, and have set env variables in .env file.
```bash
gcloud --version
gcloud auth login
gcloud config set project <your-project-id>
```

2. Ensure that the compute service is enabled for the currently selected project.
```bash
gcloud services enable compute.googleapis.com
```

3. Set permissions an run script
```bash
chmod +x deploy/01-factory-vm.sh
./deploy/01-factory-vm.sh
```

4. get the IP of the running VM and try to connect via local MQTT client to sanity check
```bash
mosquitto_sub -h $BROKER_IP -u demo -P demo123 -t "factory/#" -v
```

### Local Testing Notes:
1. load Google env variables before starting up web server:
```bash
GOOGLE_CLOUD_PROJECT="$(gcloud config get-value project)" \
GOOGLE_APPLICATION_CREDENTIALS="$PWD/api/app-bq-reader.key.json" \
uv run python main.py
```

2. Sanity check BigQuery in a second terminal window:
```bash
curl -s "http://localhost:8000/api/machines/latest?minutes=120" | jq
```