import json
import time
import logging
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("laya-playground")

MODEL_ID = "aac6fef/laya-mlx"
SCENARIOS_PATH = Path(__file__).parent / "scenarios.json"

agent = None  # populated in the startup event

def load_model():
    import laya_mlx as laya

    logger.info("Loading %s (dtype=float16, compile=True, cache_prompts=True) ...", MODEL_ID)
    t0 = time.perf_counter()
    loaded = laya.load(

        MODEL_ID,
        dtype="float16",
        compile=True,
        cache_prompts=True,

    )
    logger.info("Model loaded in %.1f ms", (time.perf_counter() - t0) * 1000)
    return loaded

def load_scenarios():
    with open(SCENARIOS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

class PredictRequest(BaseModel):
    state_text: str = Field(..., description="The input state / context text for the model.")
    questions: Dict[str, Any] = Field(
        ..., description="Typed-decision questions tree (choice / score / noul)."
    )


# fastapi app

app = FastAPI(title="Ufuk's Laya-MLX Playground")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    global agent
    agent = load_model()


@app.get("/api/scenarios")
def get_scenarios():
    return load_scenarios()


@app.post("/api/predict")
def predict(req: PredictRequest):
    if agent is None:
        raise HTTPException(status_code=503, detail="Model is still loading. Try again shortly.")

    if not req.state_text or not req.state_text.strip():
        raise HTTPException(status_code=400, detail="state_text must not be empty.")
    if not req.questions:
        raise HTTPException(status_code=400, detail="questions must not be empty.")

    t0 = time.perf_counter()
    try:
        result = agent.predict(req.state_text, req.questions)
    except Exception as exc:  # surface model/validation errors to the frontend
        logger.exception("agent.predict failed")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    latency_ms = (time.perf_counter() - t0) * 1000

    result["latency_ms"] = round(latency_ms, 3)
    return result

@app.get("/")
def serve_index():
    return FileResponse(Path(__file__).parent / "index.html")

@app.get("/favicon.ico")
def serve_favicon():
    favicon_path = Path(__file__).parent / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    raise HTTPException(status_code=404, detail="favicon.ico not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8777, reload=False)