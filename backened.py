import asyncio
import copy
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="AquaSentinel 360 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = Path(__file__).with_name("aquasentinel.db")
db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        event TEXT NOT NULL
    )
""")
db.commit()

clients: set[WebSocket] = set()
burst_active = False
tick_count = 0

state = {
    "connected": True,
    "updated_at": None,
    "zones": [],
    "incident": None,
    "events": [],
}


def now():
    return datetime.now(timezone.utc).isoformat()


def log_event(message: str):
    event = {"timestamp": now(), "message": message}
    state["events"].insert(0, event)
    state["events"] = state["events"][:30]

    db.execute(
        "INSERT INTO events(timestamp, event) VALUES (?, ?)",
        (event["timestamp"], message),
    )
    db.commit()

    if state["incident"]:
        state["incident"]["timeline"].insert(0, event)


def make_zones():
    zones = [
        {"id": "A1", "expected_flow_lph": 4200, "expected_pressure_bar": 4.1},
        {"id": "B2", "expected_flow_lph": 5100, "expected_pressure_bar": 3.8},
        {"id": "C3", "expected_flow_lph": 5800, "expected_pressure_bar": 3.6},
        {"id": "D4", "expected_flow_lph": 3900, "expected_pressure_bar": 4.0},
    ]

    for zone in zones:
        zone.update({
            "flow_lph": zone["expected_flow_lph"],
            "pressure_bar": zone["expected_pressure_bar"],
            "status": "Healthy",
            "digital_twin_mismatch": "LOW",
        })

    return zones


state["zones"] = make_zones()


def update_readings():
    """Generate demo telemetry. Replace this function with real sensor input."""
    global tick_count
    tick_count += 1

    for zone in state["zones"]:
        if burst_active and zone["id"] == "C3":
            zone["flow_lph"] = 8000
            zone["pressure_bar"] = 2.84
            zone["status"] = "Incident"
            zone["digital_twin_mismatch"] = "HIGH"
        else:
            # Small deterministic variation for a live-looking dashboard.
            variation = ((tick_count + ord(zone["id"][0])) % 5) * 12
            zone["flow_lph"] = zone["expected_flow_lph"] + variation
            zone["pressure_bar"] = round(
                zone["expected_pressure_bar"] + (variation / 1000), 2
            )
            zone["status"] = "Healthy"
            zone["digital_twin_mismatch"] = "LOW"

    state["updated_at"] = now()


def create_burst_incident():
    if state["incident"] is not None:
        return

    incident = {
        "id": f"AS-{datetime.now().strftime('%H%M%S')}",
        "type": "Pipe burst suspected",
        "zone": "C3",
        "asset": "C3 main corridor",
        "confidence": 94,
        "priority": "CRITICAL",
        "estimated_loss_lph": 800,
        "flow_change_percent": 38,
        "pressure_change_percent": -21,
        "digital_twin_mismatch": "HIGH",
        "status": "Open",
        "acknowledged": False,
        "dispatched": False,
        "created_at": now(),
        "timeline": [],
        "evidence": [
            "Flow increased by 38% against the digital twin baseline",
            "Pressure decreased by 21%",
            "Digital Twin mismatch is HIGH",
            "Abnormality persisted (compressed demo simulation)",
            "Neighboring sensor confirms abnormality",
        ],
        "recommendation": "Inspect the C3 main corridor immediately.",
    }

    state["incident"] = incident
    log_event("Flow anomaly detected in Zone C3")
    log_event("Pressure drop and Digital Twin mismatch detected")
    log_event("Pipe burst suspected — 94% prototype confidence")
    log_event("Zone C3 localized; CRITICAL priority assigned")


def snapshot():
    return copy.deepcopy(state)


async def broadcast():
    if not clients:
        return

    message = json.dumps(snapshot())
    disconnected = []

    for client in list(clients):
        try:
            await client.send_text(message)
        except Exception:
            disconnected.append(client)

    for client in disconnected:
        clients.discard(client)


async def telemetry_loop():
    while True:
        update_readings()
        await broadcast()
        await asyncio.sleep(1)


@app.on_event("startup")
async def startup():
    asyncio.create_task(telemetry_loop())


@app.get("/api/state")
async def get_state():
    return snapshot()


@app.post("/api/simulate/burst")
async def simulate_burst():
    global burst_active
    burst_active = True
    update_readings()
    create_burst_incident()
    await broadcast()
    return snapshot()


@app.post("/api/reset")
async def reset_demo():
    global burst_active
    burst_active = False
    state["incident"] = None
    state["zones"] = make_zones()
    log_event("Demo reset — all zones healthy")
    update_readings()
    await broadcast()
    return snapshot()


@app.post("/api/incident/acknowledge")
async def acknowledge_incident():
    if state["incident"]:
        state["incident"]["acknowledged"] = True
        state["incident"]["status"] = "Acknowledged"
        log_event("Operator acknowledged the incident")
    await broadcast()
    return snapshot()


@app.post("/api/incident/dispatch")
async def dispatch_technician():
    if state["incident"]:
        state["incident"]["dispatched"] = True
        state["incident"]["status"] = "Technician dispatched"
        log_event("Technician dispatch recommended for Zone C3")
    await broadcast()
    return snapshot()


@app.get("/api/what-if")
async def what_if():
    loss_rate = (
        state["incident"]["estimated_loss_lph"]
        if state["incident"]
        else 0
    )
    return {
        "prototype_estimate": True,
        "loss_rate_lph": loss_rate,
        "scenarios": [
            {"hours": hours, "additional_loss_liters": loss_rate * hours}
            for hours in (2, 6, 12)
        ],
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)

    try:
        await websocket.send_text(json.dumps(snapshot()))
        while True:
            # Keep the connection open. Telemetry is pushed by telemetry_loop.
            await websocket.receive_text()
    except WebSocketDisconnect:
        clients.discard(websocket)
    except Exception:
        clients.discard(websocket)
