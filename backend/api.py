import os
import json
import uuid
import time
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

from logging_config import get_logger

log = get_logger(__name__)

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from livekit.api import LiveKitAPI, AccessToken, VideoGrants, CreateRoomRequest
from livekit.api.agent_dispatch_service import CreateAgentDispatchRequest

from database import (
    init_db, upsert_user, get_available_slots, create_appointment,
    get_user_appointments, cancel_appointment_by_id,
    modify_appointment_by_id, save_call_summary, get_call_summary,
)

log.info("API module loading — initialising database")
init_db()

app = FastAPI(title="Mykare Voice AI API", version="1.0.0")

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET", "")

# Warn early if critical env vars are missing
for var, val in [
    ("LIVEKIT_URL", LIVEKIT_URL),
    ("LIVEKIT_API_KEY", LIVEKIT_API_KEY),
    ("LIVEKIT_API_SECRET", LIVEKIT_API_SECRET),
]:
    if not val:
        log.critical("Missing required env var: %s — check your .env file", var)


def get_lk_api() -> LiveKitAPI:
    return LiveKitAPI(
        url=LIVEKIT_URL,
        api_key=LIVEKIT_API_KEY,
        api_secret=LIVEKIT_API_SECRET,
    )


# ── Request / Response logging middleware ─────────────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    t0 = time.perf_counter()
    log.debug("REQUEST  %s %s | client=%s", request.method, request.url.path, request.client)
    try:
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        level = log.info if response.status_code < 400 else log.warning
        level(
            "RESPONSE %s %s | status=%d | %.0f ms",
            request.method, request.url.path, response.status_code, elapsed_ms
        )
        return response
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        log.error(
            "RESPONSE %s %s | UNHANDLED EXCEPTION | %.0f ms: %s",
            request.method, request.url.path, elapsed_ms, exc, exc_info=True
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── Request / Response Models ─────────────────────────────────────────────────

class StartCallRequest(BaseModel):
    user_name: Optional[str] = "Patient"
    phone_number: Optional[str] = ""

class BookRequest(BaseModel):
    phone_number: str
    date: str
    time_slot: str
    notes: Optional[str] = ""

class ModifyRequest(BaseModel):
    phone_number: str
    appointment_id: int
    new_date: str
    new_time: str

class SummaryRequest(BaseModel):
    session_id: str
    user_id: Optional[int] = None
    phone_number: str
    user_name: str
    summary: str
    appointments: list = []
    preferences: Optional[str] = ""
    intent: Optional[str] = ""


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    log.debug("Health check")
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.post("/api/start-call")
async def start_call(req: StartCallRequest):
    """Create a LiveKit room, generate user token, dispatch the agent."""
    log.info(
        "start_call | user_name=%r phone=%r",
        req.user_name, req.phone_number
    )

    if not all([LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET]):
        log.error("start_call FAILED — LiveKit credentials not configured")
        raise HTTPException(500, "LiveKit credentials not configured. Check .env file.")

    room_name = f"mykare-{uuid.uuid4().hex[:8]}"
    user_identity = f"user-{uuid.uuid4().hex[:6]}"
    log.debug("start_call | room=%s identity=%s", room_name, user_identity)

    lk = get_lk_api()

    # Create the room
    t0 = time.perf_counter()
    try:
        await lk.room.create_room(
            CreateRoomRequest(name=room_name, empty_timeout=300, max_participants=5)
        )
        log.info("LiveKit room created | room=%s (%.0f ms)", room_name, (time.perf_counter() - t0) * 1000)
    except Exception as exc:
        log.error("LiveKit create_room FAILED | room=%s: %s", room_name, exc, exc_info=True)
        raise HTTPException(500, f"Failed to create room: {exc}")

    # Generate user token
    try:
        token = (
            AccessToken(api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)
            .with_identity(user_identity)
            .with_name(req.user_name or "Patient")
            .with_grants(VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            ))
            .to_jwt()
        )
        log.debug("Token generated | identity=%s room=%s", user_identity, room_name)
    except Exception as exc:
        log.error("Token generation FAILED | room=%s: %s", room_name, exc, exc_info=True)
        raise HTTPException(500, f"Token generation failed: {exc}")

    # Dispatch the agent
    t1 = time.perf_counter()
    try:
        await lk.agent_dispatch.create_dispatch(
            CreateAgentDispatchRequest(
                agent_name="mykare-healthcare-agent",
                room=room_name,
                metadata=json.dumps({
                    "phone_number": req.phone_number,
                    "user_name": req.user_name,
                }),
            )
        )
        log.info(
            "Agent dispatched | room=%s agent=mykare-healthcare-agent (%.0f ms)",
            room_name, (time.perf_counter() - t1) * 1000
        )
    except Exception as exc:
        # Non-fatal: agent may auto-connect if worker is listening
        log.warning(
            "Agent dispatch warning | room=%s: %s — agent may still connect via auto-dispatch",
            room_name, exc
        )

    await lk.aclose()

    log.info(
        "start_call SUCCESS | room=%s identity=%s total=%.0f ms",
        room_name, user_identity, (time.perf_counter() - t0) * 1000
    )
    return {
        "token": token,
        "room_name": room_name,
        "ws_url": LIVEKIT_URL,
        "user_identity": user_identity,
    }


@app.get("/api/slots")
async def get_slots(date: Optional[str] = None):
    log.info("get_slots | date=%s", date or "next-7-days")
    try:
        slots = get_available_slots(date)
        log.info("get_slots | returning %d date(s)", len(slots))
        return {"slots": slots}
    except Exception as exc:
        log.error("get_slots FAILED: %s", exc, exc_info=True)
        raise HTTPException(500, str(exc))


@app.post("/api/appointments")
async def book(req: BookRequest):
    log.info(
        "book | phone=%s date=%s time=%s notes=%r",
        req.phone_number, req.date, req.time_slot, req.notes
    )
    try:
        user = upsert_user(req.phone_number, "")
        result = create_appointment(user["user_id"], req.date, req.time_slot, req.notes or "")
        if not result["success"]:
            log.warning(
                "book REJECTED | phone=%s date=%s time=%s reason=%r",
                req.phone_number, req.date, req.time_slot, result.get("error")
            )
            raise HTTPException(409, result.get("error", "Booking failed"))
        log.info("book SUCCESS | appt_id=%d", result["appointment_id"])
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log.error("book EXCEPTION | phone=%s: %s", req.phone_number, exc, exc_info=True)
        raise HTTPException(500, str(exc))


@app.get("/api/appointments/{phone_number}")
async def get_appointments(phone_number: str):
    log.info("get_appointments | phone=%s", phone_number)
    try:
        user = upsert_user(phone_number, "")
        appointments = get_user_appointments(user["user_id"])
        log.info("get_appointments | phone=%s returning=%d", phone_number, len(appointments))
        return {"appointments": appointments, "phone": phone_number}
    except Exception as exc:
        log.error("get_appointments EXCEPTION | phone=%s: %s", phone_number, exc, exc_info=True)
        raise HTTPException(500, str(exc))


@app.delete("/api/appointments/{appointment_id}")
async def cancel(appointment_id: int, phone_number: str):
    log.info("cancel | appt_id=%d phone=%s", appointment_id, phone_number)
    try:
        user = upsert_user(phone_number, "")
        result = cancel_appointment_by_id(appointment_id, user["user_id"])
        if not result["success"]:
            log.warning(
                "cancel FAILED | appt_id=%d reason=%r", appointment_id, result.get("error")
            )
            raise HTTPException(404, result.get("error", "Not found"))
        log.info("cancel SUCCESS | appt_id=%d", appointment_id)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log.error("cancel EXCEPTION | appt_id=%d: %s", appointment_id, exc, exc_info=True)
        raise HTTPException(500, str(exc))


@app.put("/api/appointments/{appointment_id}")
async def modify(appointment_id: int, req: ModifyRequest):
    log.info(
        "modify | appt_id=%d phone=%s new_date=%s new_time=%s",
        appointment_id, req.phone_number, req.new_date, req.new_time
    )
    try:
        user = upsert_user(req.phone_number, "")
        result = modify_appointment_by_id(appointment_id, user["user_id"], req.new_date, req.new_time)
        if not result["success"]:
            log.warning(
                "modify FAILED | appt_id=%d reason=%r", appointment_id, result.get("error")
            )
            raise HTTPException(400, result.get("error", "Error"))
        log.info("modify SUCCESS | appt_id=%d -> %s %s", appointment_id, req.new_date, req.new_time)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        log.error("modify EXCEPTION | appt_id=%d: %s", appointment_id, exc, exc_info=True)
        raise HTTPException(500, str(exc))


@app.post("/api/summary")
async def create_summary(req: SummaryRequest):
    log.info(
        "create_summary | session=%s phone=%s intent=%r appts=%d",
        req.session_id, req.phone_number, req.intent, len(req.appointments)
    )
    try:
        result = save_call_summary(
            session_id=req.session_id,
            user_id=req.user_id,
            phone_number=req.phone_number,
            user_name=req.user_name,
            summary=req.summary,
            appointments=req.appointments,
            preferences=req.preferences or "",
            intent=req.intent or "",
        )
        log.info("create_summary SUCCESS | session=%s", req.session_id)
        return result
    except Exception as exc:
        log.error("create_summary EXCEPTION | session=%s: %s", req.session_id, exc, exc_info=True)
        raise HTTPException(500, str(exc))


@app.get("/api/summary/{session_id}")
async def fetch_summary(session_id: str):
    log.info("fetch_summary | session=%s", session_id)
    try:
        summary = get_call_summary(session_id)
        if not summary:
            log.warning("fetch_summary NOT_FOUND | session=%s", session_id)
            raise HTTPException(404, "Summary not found")
        log.info("fetch_summary SUCCESS | session=%s user=%r", session_id, summary.get("user_name"))
        return summary
    except HTTPException:
        raise
    except Exception as exc:
        log.error("fetch_summary EXCEPTION | session=%s: %s", session_id, exc, exc_info=True)
        raise HTTPException(500, str(exc))


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("API_HOST", "0.0.0.0")
    port = int(os.getenv("API_PORT", "8000"))
    log.info("Starting FastAPI server | host=%s port=%d", host, port)
    uvicorn.run("api:app", host=host, port=port, reload=True)
