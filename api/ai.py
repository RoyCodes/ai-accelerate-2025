# api/ai.py
import os, time
from typing import List, Dict
from fastapi import APIRouter
from pydantic import BaseModel
from google.cloud import bigquery
from google.api_core.exceptions import GoogleAPICallError, BadRequest

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION   = os.environ.get("VERTEX_LOCATION", "us-central1")
DATASET    = os.environ.get("BQ_DATASET", "cookie_factory_mqtt")
TABLE      = os.environ.get("BQ_TABLE",   "telemetry")

# Keep your Vertex bits if you need them later
from vertexai import init as vertex_init
from vertexai.generative_models import GenerativeModel, Part
MODEL_NAME = os.environ.get("VERTEX_MODEL", "gemini-1.5-flash-002")

router = APIRouter(prefix="/api/ai", tags=["ai"])

class ChatIn(BaseModel):
    prompt: str
    minutes: int = 15  # how much telemetry to consider

def _resolve_co2_column(client: bigquery.Client) -> str:
    """
    Look up which CO₂ column exists in the table: 'co_2_kg_per_min' (current) or
    the older 'co2_kg_per_min'. Default to 'co_2_kg_per_min' if both present or neither found.
    """
    sql = f"""
    SELECT column_name
    FROM `{PROJECT_ID}.{DATASET}.INFORMATION_SCHEMA.COLUMNS`
    WHERE table_name=@table
      AND column_name IN ('co_2_kg_per_min', 'co2_kg_per_min')
    ORDER BY CASE column_name
               WHEN 'co_2_kg_per_min' THEN 0  -- prefer the canonical name
               ELSE 1
             END
    LIMIT 1
    """
    job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("table", "STRING", TABLE)]
        ),
    )
    rows = list(job)
    if rows:
        return rows[0]["column_name"]
    # Fallback to canonical name
    return "co_2_kg_per_min"

def _fetch_latest(minutes: int) -> List[Dict]:
    assert PROJECT_ID, "GOOGLE_CLOUD_PROJECT not set"
    client = bigquery.Client(project=PROJECT_ID)

    co2_col = _resolve_co2_column(client)  # 'co_2_kg_per_min' or 'co2_kg_per_min'

    sql = f"""
    SELECT
      machine_id,
      name,
      type,
      TIMESTAMP_MILLIS(CAST(ts*1000 AS INT64)) AS ts,
      power_w,
      `{co2_col}` AS co2_kg_per_min,
      scrap_rate_pct
    FROM `{PROJECT_ID}.{DATASET}.{TABLE}`
    WHERE TIMESTAMP_MILLIS(CAST(ts*1000 AS INT64)) >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @mins MINUTE)
    QUALIFY ROW_NUMBER() OVER (PARTITION BY machine_id ORDER BY ts DESC) = 1
    ORDER BY machine_id
    """
    job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("mins", "INT64", minutes)]
        ),
    )
    return [dict(row) for row in job]

def _system_prompt() -> str:
    return (
        "You are the Cookie Factory Copilot. "
        "Analyze the latest machine telemetry and answer briefly with clear, actionable bullets. "
        "If data is missing, say so. Mention machine names and timestamps with metrics. "
        "If scrap_rate_pct > 1.0, flag an alert."
    )

@router.post("/chat")
def chat(req: ChatIn):
    try:
        rows = _fetch_latest(req.minutes)
    except BadRequest as e:
        # Return a JSON error the UI can render cleanly
        return {"error": f"BigQuery error: {e}", "output": "", "machine_count": 0}
    except GoogleAPICallError as e:
        return {"error": f"BigQuery call failed: {e}", "output": "", "machine_count": 0}

    # Construct a compact context JSON block
    context = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "machines": rows,
    }

    # Call Vertex (non-streaming)
    try:
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
    except Exception as e:
        # Return an error string but still a valid JSON body
        return {
            "error": f"Vertex error: {e}",
            "output": "",
            "machine_count": len(rows),
        }

    return {"error": "", "output": text, "machine_count": len(rows)}
