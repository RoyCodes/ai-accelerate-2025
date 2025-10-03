# FastAPI backend and Mesop mount

import mesop as me
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware
import subprocess, sys
from pathlib import Path

# import Mesop page from UI folder
import ui.home

# Initialize FastAPI app
app = FastAPI()

@app.post("/api/generate/start")
def generate_start():
    # Start up generate.py
    script = Path(__file__).resolve().parent / "api" / "generate.py"
    subprocess.Popen([sys.executable, str(script)])
    return {"message": "Generation started."}   

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