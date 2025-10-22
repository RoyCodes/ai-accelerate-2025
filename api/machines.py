# api/machines.py
import os
from fastapi import APIRouter, Query
from google.cloud import bigquery

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
router = APIRouter()

@router.get("/latest")
def latest_metrics(minutes: int = Query(5, ge=1, le=1440)):
    if not PROJECT_ID:
        return {"error": "GOOGLE_CLOUD_PROJECT not set"}

    client = bigquery.Client(project=PROJECT_ID)
    sql = f"""
    WITH t AS (
      SELECT
        machine_id,
        name,
        type,
        TIMESTAMP_MILLIS(CAST(ts * 1000 AS INT64)) AS ts,
        power_w,
        co_2_kg_per_min AS co2_kg_per_min,
        scrap_rate_pct
      FROM `{PROJECT_ID}.cookie_factory_mqtt.telemetry`
      WHERE TIMESTAMP_MILLIS(CAST(ts * 1000 AS INT64)) >=
            TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @m MINUTE)
    )
    SELECT * EXCEPT(rn)
    FROM (
      SELECT t.*, ROW_NUMBER() OVER (PARTITION BY machine_id ORDER BY ts DESC) AS rn
      FROM t
    )
    WHERE rn = 1
    ORDER BY ts DESC
    """
    job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            query_parameters=[bigquery.ScalarQueryParameter("m", "INT64", minutes)]
        ),
    )
    rows = list(job.result())
    return {
        "items": [
            {
                "machine_id": r["machine_id"],
                "name": r["name"],
                "type": r["type"],
                "ts": r["ts"].isoformat(),
                "power_w": r["power_w"],
                "co2_kg_per_min": r["co2_kg_per_min"],
                "scrap_rate_pct": r["scrap_rate_pct"],
            }
            for r in rows
        ],
        "count": len(rows),
    }
