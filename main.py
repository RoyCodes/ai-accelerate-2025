# FastAPI backend and Mesop mount

import mesop as me
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware
# import subprocess, sys
# from pathlib import Path

# import Mesop page from UI folder
import ui.home

from api.machines import router as machines_router
from api.workers import generate_new_worker

# Initialize FastAPI app
app = FastAPI()

# ---- Generate a Machine ----
app.include_router(machines_router, prefix="/api/machines", tags=["machines"])

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