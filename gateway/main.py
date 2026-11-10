"""HTTP front of the gateway. Run from the project root:  uvicorn gateway.main:app --host 0.0.0.0 --port 8000"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import settings
from .db import Store
from .engine import COMMANDS, Engine

cfg = settings.load()
store = Store(settings.resolve(cfg["gateway"]["db_path"]))
engine = Engine(cfg, store)


class Telemetry(BaseModel):
    node_id: str
    seq: int
    uptime_ms: int
    bus_v: float
    current_a: float
    power_w: float
    vsense_v: float | None = None
    relay_on: bool | None = None
    rssi: int | None = None
    fw: str | None = None


class CommandIn(BaseModel):
    node_id: str = "B"
    command: str
    text: str = ""


class ExperimentIn(BaseModel):
    name: str
    scenario: str = "normal"
    node: str = "A"
    field: str = "current_a"
    params: dict = {}


async def watchdog():
    while True:
        await asyncio.sleep(1)
        engine.tick()


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(watchdog())
    yield
    task.cancel()


app = FastAPI(title="GridSentinel Edge gateway", lifespan=lifespan)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/telemetry")
def telemetry(t: Telemetry):
    engine.ingest(t.model_dump())
    return {"ok": True}


@app.get("/command/{node_id}")
def next_command(node_id: str):
    return store.next_command(node_id) or {"id": 0, "command": "none", "text": ""}


@app.post("/command/{cmd_id}/ack")
def ack(cmd_id: int):
    store.ack_command(cmd_id)
    return {"ok": True}


@app.post("/command")
def new_command(c: CommandIn):
    if c.command not in COMMANDS:
        raise HTTPException(422, f"command must be one of {sorted(COMMANDS)}")
    return {"id": store.queue_command(c.node_id, c.command, c.text)}


@app.get("/status")
def status():
    return engine.status()


@app.post("/experiment/start")
def experiment_start(e: ExperimentIn):
    try:
        return {"id": engine.start_experiment(e.name, e.scenario, e.node, e.field, e.params)}
    except ValueError as err:
        raise HTTPException(422, str(err))


@app.post("/experiment/stop")
def experiment_stop():
    engine.stop_experiment()
    return {"ok": True}
