# FastAPI backend and Mesop mount

import mesop as me
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware
import subprocess, sys
from pathlib import Path

# import Mesop page from UI folder
import ui.home

# import your generators
from api.machines import generate_new_machine
from api.workers import generate_new_worker

# Initialize FastAPI app
app = FastAPI()

# --- Start up aMQTT Telemetry Generator ---
@app.post("/api/generate/start")
def generate_start():
    # Start up generate.py
    script = Path(__file__).resolve().parent / "api" / "generate.py"
    subprocess.Popen([sys.executable, str(script)])
    return {"message": "Generation started."}   

# ---- Generate a Machine ----
@app.post("/api/machines/generate")
def machines_generate():
    return generate_new_machine() 

# ---- Generate a Worker ----
@app.post("/api/workers/generate")
def workers_generate():
    return generate_new_worker() 

app.mount(
    "/",
    WSGIMiddleware(
        me.create_wsgi_app() 
    ),
)

# Run the app with Uvicorn
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )