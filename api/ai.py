# api/ai.py
import os, time
from typing import List, Dict
from fastapi import APIRouter
from pydantic import BaseModel
from google.cloud import bigquery
from vertexai import init as vertex_init
from vertexai.generative_models import GenerativeModel, Part
from google.api_core.exceptions import GoogleAPICallError, BadRequest

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION   = os.environ.get("VERTEX_LOCATION", "us-central1")
DATASET    = os.environ.get("BQ_DATASET", "cookie_factory_mqtt")
TABLE      = os.environ.get("BQ_TABLE",   "telemetry")
MODEL_NAME = os.environ.get("VERTEX_MODEL", "gemini-1.5-flash-002")

router = APIRouter(prefix="/api/ai", tags=["ai"])

class ChatIn(BaseModel):
    prompt: str
    minutes: int = 15  # how much telemetry to consider


def _fetch_latest(minutes: int) -> List[Dict]:
    if not PROJECT_ID:
        # Return an empty list so callers can handle gracefully
        return []

    client = bigquery.Client(project=PROJECT_ID)
    sql = f"""
    -- Latest row per machine over the last @mins minutes
    WITH recent AS (
      SELECT
        machine_id,
        name,
        type,
        TIMESTAMP_MILLIS(CAST(ts * 1000 AS INT64)) AS ts,
        power_w,
        COALESCE(co2_kg_per_min, co_2_kg_per_min) AS co2_kg_per_min,
        scrap_rate_pct,
        ROW_NUMBER() OVER (PARTITION BY machine_id ORDER BY ts DESC) AS rn
      FROM `{PROJECT_ID}.{DATASET}.{TABLE}`
      WHERE ts >= UNIX_SECONDS(TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @mins MINUTE))
    )
    SELECT machine_id, name, type, ts, power_w, co2_kg_per_min, scrap_rate_pct
    FROM recent
    WHERE rn = 1
    ORDER BY machine_id
    """
    job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("mins", "INT64", minutes)]
        ),
    )
    # Materialize the results now; avoids lazy iteration surprises
    return [dict(row) for row in job.result()]


def _system_prompt() -> str:
    return (
        "You are the Cookie Factory Copilot. "
        "You analyze the latest machine telemetry and answer briefly with clear actions. "
        "If data is missing, say so. Prefer bullets. "
        "Always mention machine names and timestamps when citing metrics. "
        "If scrap_rate_pct > 1.0, flag an alert."
    )


@router.post("/chat")
def chat(req: ChatIn):
    if not PROJECT_ID:
        return {"error": "GOOGLE_CLOUD_PROJECT not set", "output": ""}

    try:
        # Pull a small, fresh snapshot for grounding
        rows = _fetch_latest(req.minutes)
    except (BadRequest, GoogleAPICallError) as e:
        # Return a readable error to the UI instead of a 500
        return {"error": f"BigQuery error: {e}", "output": "", "machine_count": 0}

    # Construct a compact context JSON block
    context = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "machines": rows,
    }

    vertex_init(project=PROJECT_ID, location=LOCATION)
    model = GenerativeModel(MODEL_NAME)

    user = (
        f"{req.prompt}\n\n"
        f"Here is the latest telemetry JSON:\n"
        f"{context}\n\n"
        "Answer using the telemetry above."
    )

    resp = model.generate_content(
        [Part.from_text(_system_prompt()), Part.from_text(user)],
        safety_settings=None,
        generation_config={"temperature": 0.3, "max_output_tokens": 512},
    )
    text = getattr(resp, "text", None) or "(no response)"
    return {"output": text, "machine_count": len(rows)}
