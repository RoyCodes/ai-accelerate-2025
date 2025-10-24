## Smart Cookie — Industry 5.0 Factory Copilot

A lightweight end-to-end demo showing live factory telemetry flowing into Google Cloud, surfaced in a Mesop UI, and reasoned over with Vertex AI. Built for the AI Accelerate hackathon (Google Cloud × Fivetran × Elastic).

### Quick Overview

Live telemetry → MQTT (simulated cookie line: Mixer, Kneader, Cutter, Oven, Cooler, Packer)

Ingest → Custom Fivetran Connector SDK pumps MQTT → BigQuery

Serve → FastAPI backs a Mesop UI (machines, workers, and chat)

Reason → Vertex AI (Gemini 2.5) answers questions about the line and suggests actions

### Architecture (at a glance)

```
MQTT simulator  -->  Fivetran connector  -->  BigQuery
                                         \
                                          --> FastAPI (machines API, AI API) --> Mesop UI (machines + workers + chat)
                                                              |
                                                              --> Vertex AI (Gemini) for grounded answers
```

### Technologies Used:
1. Fivetran Connector SDK (custom connector → BigQuery)
2. Google Cloud: BigQuery, Vertex AI (Gemini 2.5)
3. fastAPI
4. Mesop

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

### License

MIT (or your preferred OSS license). Add the LICENSE file at repo root.

### Acknowledgments

Google Cloud (Vertex AI, BigQuery)

Fivetran Connector SDK

Mesop team for a delightful Python-first UI framework