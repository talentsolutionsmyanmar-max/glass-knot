"""Glass Knot FastAPI — dashboard + poll API."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import config
from app.api_counter import read_counter
from app.nansen import NansenClient
from app.pipeline import run_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("glass_knot")

_poll_task: asyncio.Task | None = None


async def _background_poll() -> None:
    while True:
        try:
            await asyncio.to_thread(run_pipeline)
        except Exception:  # noqa: BLE001
            log.exception("background poll failed")
        await asyncio.sleep(config.POLL_INTERVAL_SEC)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _poll_task
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not config.API_CALLS_PATH.exists():
        config.API_CALLS_PATH.write_text(
            json.dumps(
                {
                    "total": 0,
                    "by_endpoint": {},
                    "last_call_at": None,
                    "updated_at": None,
                    "target": 1000,
                    "note": "Counts every live Nansen request (demo/fixture loads do not increment).",
                },
                indent=2,
            )
            + "\n"
        )
    try:
        await asyncio.to_thread(run_pipeline)
    except Exception:  # noqa: BLE001
        log.exception("initial pipeline failed")
    _poll_task = asyncio.create_task(_background_poll())
    yield
    if _poll_task:
        _poll_task.cancel()
        try:
            await _poll_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="Glass Knot",
    description=(
        "Solana Smart Money knot inspector. "
        "SM dex-trades → BFS related-wallets → grade "
        "FARM_CLUSTER | SOLO_SM | RESEARCH | FAIL. "
        "PAPER · INSPECT ONLY · NO COPY-TRADE."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(config.STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "product": "Glass Knot",
        "demo_mode": config.DEMO_MODE,
        "policy": "PAPER_INSPECT_ONLY",
        "grades": list(config.GRADES),
        "has_latest": config.LATEST_PATH.exists(),
        "api_calls": read_counter(),
    }


@app.get("/api/latest")
def latest() -> JSONResponse:
    if not config.LATEST_PATH.exists():
        return JSONResponse(
            {"error": "no data yet", "demo_mode": config.DEMO_MODE, "product": "Glass Knot"},
            status_code=404,
        )
    return JSONResponse(content=json.loads(config.LATEST_PATH.read_text()))


@app.get("/api/calls")
def api_calls() -> dict[str, Any]:
    return read_counter()


@app.post("/api/poll")
def poll_now() -> JSONResponse:
    payload = run_pipeline(NansenClient())
    return JSONResponse(payload)


def main() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host=config.HOST, port=config.PORT, reload=False)


if __name__ == "__main__":
    main()
