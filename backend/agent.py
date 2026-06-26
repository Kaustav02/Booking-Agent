import asyncio
import json
import uuid
import time
import os
import traceback
from datetime import datetime
from dotenv import load_dotenv
import aiohttp
import openai as openai_sdk

load_dotenv()

# Fix SSL cert verification on macOS with python.org installer.
# Patch ssl.create_default_context so ALL connections in this process
# (including aiohttp inside livekit plugins) use certifi's CA bundle.
import certifi
import ssl as _ssl_module

os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()

_orig_create_default_context = _ssl_module.create_default_context
def _certifi_default_context(*args, **kwargs):
    ctx = _orig_create_default_context(*args, **kwargs)
    ctx.load_verify_locations(cafile=certifi.where())
    return ctx
_ssl_module.create_default_context = _certifi_default_context

from logging_config import get_logger

log = get_logger(__name__)

from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli
from livekit.agents.llm import function_tool, ChatMessage
from livekit.plugins import deepgram, cartesia
from livekit.plugins import openai as lk_openai

from database import (
    init_db, upsert_user, get_available_slots, create_appointment,
    get_user_appointments, cancel_appointment_by_id,
    modify_appointment_by_id, save_call_summary,
)

log.info("Agent module loading — initialising database")
init_db()

SYSTEM_PROMPT = """You are Aria, a warm and professional AI healthcare front-desk assistant for Mykare Health Clinic.

Your goal is to help patients book, manage, and cancel appointments efficiently.

TODAY'S DATE: {today}
CLINIC HOURS: Monday–Saturday, 9 AM – 5 PM

CONVERSATION FLOW:
1. Greet warmly and introduce yourself as Aria
2. Ask for name AND phone number early (needed for identify_user tool)
3. Call identify_user tool immediately after getting phone number
4. Understand the patient's need (book / check / cancel / modify appointment)
5. Use the appropriate tools
6. Confirm all actions clearly
7. When conversation is complete, call end_conversation

RULES:
- Keep responses to 1-3 sentences — you're on a phone call
- Always confirm appointment details (date, time) before booking
- After booking/cancelling/modifying, always confirm to the patient
- Extract: name, phone, date, time, intent from conversation
- Never book without calling identify_user first
- If a slot is unavailable, suggest alternatives from fetch_slots

TONE: Warm, empathetic, professional — like a kind receptionist."""


class HealthcareAgent(Agent):
    def __init__(self, ctx: JobContext):
        super().__init__(
            instructions=SYSTEM_PROMPT.format(
                today=datetime.now().strftime("%A, %B %d, %Y")
            )
        )
        self._ctx = ctx
        self._session_id = str(uuid.uuid4())[:8]
        self._user_id: int | None = None
        self._user_name: str = ""
        self._user_phone: str = ""
        self._tool_call_count: int = 0
        self._call_start: float = time.perf_counter()
        self._transcript: list[dict] = []  # running log of every turn this call

        log.info(
            "HealthcareAgent initialised | session=%s room=%s",
            self._session_id, ctx.room.name
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _emit(self, event_type: str, tool: str = "", message: str = "", data: dict = None):
        payload = {
            "type": event_type,
            "tool": tool,
            "message": message,
            "data": data or {},
            "timestamp": datetime.now().isoformat(),
        }
        try:
            await self._ctx.room.local_participant.publish_data(
                json.dumps(payload).encode(),
                reliable=True,
            )
            log.debug("emit | type=%s tool=%s msg=%r", event_type, tool, message)
        except Exception as exc:
            log.error(
                "emit FAILED | type=%s tool=%s: %s", event_type, tool, exc, exc_info=True
            )

    def _tool_start_log(self, tool: str, **kwargs) -> float:
        self._tool_call_count += 1
        log.info(
            "TOOL_START [#%d] | session=%s tool=%s | %s",
            self._tool_call_count, self._session_id, tool,
            " ".join(f"{k}={v!r}" for k, v in kwargs.items()),
        )
        return time.perf_counter()

    def _tool_end_log(self, tool: str, t0: float, success: bool, **kwargs):
        elapsed_ms = (time.perf_counter() - t0) * 1000
        level = log.info if success else log.warning
        level(
            "TOOL_END | session=%s tool=%s success=%s elapsed=%.0f ms | %s",
            self._session_id, tool, success, elapsed_ms,
            " ".join(f"{k}={v!r}" for k, v in kwargs.items()),
        )

    # ── Tools ─────────────────────────────────────────────────────────────────

    @function_tool
    async def identify_user(self, phone_number: str, name: str = "") -> str:
        """
        Identify or register a patient using their phone number. Call this FIRST before any other tool.

        Args:
            phone_number: Patient's phone number (used as unique identifier)
            name: Patient's full name
        """
        t0 = self._tool_start_log("identify_user", phone=phone_number, name=name)
        await self._emit("tool_start", "identify_user", "Identifying patient...")

        try:
            result = upsert_user(phone_number.strip(), name.strip())
            self._user_id = result["user_id"]
            self._user_name = result["name"] or name
            self._user_phone = phone_number

            status = "NEW" if result["is_new"] else "RETURNING"
            msg = f"Patient {status.lower()}: {self._user_name}"
            await self._emit("tool_result", "identify_user", msg, result)
            self._tool_end_log(
                "identify_user", t0, True,
                user_id=self._user_id, status=status, name=self._user_name
            )
            return json.dumps({
                "user_id": result["user_id"],
                "name": result["name"] or name,
                "phone": phone_number,
                "is_returning": not result["is_new"],
            })
        except Exception as exc:
            log.error(
                "identify_user EXCEPTION | session=%s phone=%s: %s",
                self._session_id, phone_number, exc, exc_info=True
            )
            await self._emit("tool_result", "identify_user", f"Error: {exc}")
            return json.dumps({"error": str(exc)})

    @function_tool
    async def fetch_slots(self, date: str = "") -> str:
        """
        Fetch available appointment slots. Returns available dates and times.

        Args:
            date: Specific date in YYYY-MM-DD format. Leave empty to get next 7 days.
        """
        t0 = self._tool_start_log("fetch_slots", date=date or "next-7-days")
        await self._emit("tool_start", "fetch_slots", "Fetching available slots...")

        try:
            slots = get_available_slots(date.strip() if date else None)
            total_times = sum(len(s["available_times"]) for s in slots)
            msg = f"Found {len(slots)} day(s) with {total_times} available slot(s)"
            await self._emit("tool_result", "fetch_slots", msg, {"slots": slots})
            self._tool_end_log("fetch_slots", t0, True, days=len(slots), slots=total_times)

            if not slots:
                return json.dumps({"slots": [], "message": "No available slots found. Please try different dates."})
            return json.dumps({"slots": slots})
        except Exception as exc:
            log.error(
                "fetch_slots EXCEPTION | session=%s date=%s: %s",
                self._session_id, date, exc, exc_info=True
            )
            await self._emit("tool_result", "fetch_slots", f"Error: {exc}")
            return json.dumps({"error": str(exc)})

    @function_tool
    async def book_appointment(self, date: str, time_slot: str, notes: str = "") -> str:
        """
        Book an appointment for the currently identified patient.

        Args:
            date: Appointment date in YYYY-MM-DD format (e.g., "2026-06-26")
            time_slot: Time slot (e.g., "9:00 AM", "2:00 PM")
            notes: Optional notes or reason for visit
        """
        t0 = self._tool_start_log(
            "book_appointment", user_id=self._user_id, date=date, time=time_slot
        )

        if not self._user_id:
            log.warning(
                "book_appointment BLOCKED | session=%s — identify_user not called first",
                self._session_id
            )
            return json.dumps({"success": False, "error": "Patient not identified. Please call identify_user first."})

        await self._emit("tool_start", "book_appointment", f"Booking {date} at {time_slot}...")

        try:
            result = create_appointment(self._user_id, date.strip(), time_slot.strip(), notes.strip())
            success = result["success"]

            if success:
                msg = f"Booked: {date} at {time_slot}"
            else:
                msg = result.get("error", "Booking failed")

            await self._emit("tool_result", "book_appointment", msg, result)
            self._tool_end_log(
                "book_appointment", t0, success,
                appt_id=result.get("appointment_id"), date=date, time=time_slot
            )
            return json.dumps(result)
        except Exception as exc:
            log.error(
                "book_appointment EXCEPTION | session=%s user_id=%s date=%s time=%s: %s",
                self._session_id, self._user_id, date, time_slot, exc, exc_info=True
            )
            await self._emit("tool_result", "book_appointment", f"Error: {exc}")
            return json.dumps({"success": False, "error": str(exc)})

    @function_tool
    async def retrieve_appointments(self) -> str:
        """
        Retrieve all appointments for the currently identified patient.
        """
        t0 = self._tool_start_log("retrieve_appointments", user_id=self._user_id)

        if not self._user_id:
            log.warning(
                "retrieve_appointments BLOCKED | session=%s — no user identified",
                self._session_id
            )
            return json.dumps({"success": False, "error": "Patient not identified."})

        await self._emit("tool_start", "retrieve_appointments", "Fetching your appointments...")

        try:
            appointments = get_user_appointments(self._user_id)
            active = [a for a in appointments if a["status"] == "booked"]
            msg = f"Found {len(active)} active / {len(appointments)} total appointment(s)"
            await self._emit("tool_result", "retrieve_appointments", msg, {"appointments": appointments})
            self._tool_end_log(
                "retrieve_appointments", t0, True,
                total=len(appointments), active=len(active)
            )
            return json.dumps({"appointments": appointments, "count": len(appointments)})
        except Exception as exc:
            log.error(
                "retrieve_appointments EXCEPTION | session=%s user_id=%s: %s",
                self._session_id, self._user_id, exc, exc_info=True
            )
            await self._emit("tool_result", "retrieve_appointments", f"Error: {exc}")
            return json.dumps({"error": str(exc)})

    @function_tool
    async def cancel_appointment(self, appointment_id: int) -> str:
        """
        Cancel a specific appointment by its ID.

        Args:
            appointment_id: The numeric ID of the appointment to cancel
        """
        t0 = self._tool_start_log(
            "cancel_appointment", appt_id=appointment_id, user_id=self._user_id
        )

        if not self._user_id:
            log.warning("cancel_appointment BLOCKED | session=%s — no user", self._session_id)
            return json.dumps({"success": False, "error": "Patient not identified."})

        await self._emit("tool_start", "cancel_appointment", f"Cancelling appointment #{appointment_id}...")

        try:
            result = cancel_appointment_by_id(appointment_id, self._user_id)
            success = result["success"]
            msg = "Cancelled successfully" if success else result.get("error", "Error")
            await self._emit("tool_result", "cancel_appointment", msg, result)
            self._tool_end_log("cancel_appointment", t0, success, appt_id=appointment_id)
            return json.dumps(result)
        except Exception as exc:
            log.error(
                "cancel_appointment EXCEPTION | session=%s appt_id=%d: %s",
                self._session_id, appointment_id, exc, exc_info=True
            )
            await self._emit("tool_result", "cancel_appointment", f"Error: {exc}")
            return json.dumps({"success": False, "error": str(exc)})

    @function_tool
    async def modify_appointment(self, appointment_id: int, new_date: str, new_time: str) -> str:
        """
        Reschedule an existing appointment to a new date and time.

        Args:
            appointment_id: The numeric ID of the appointment to modify
            new_date: New date in YYYY-MM-DD format
            new_time: New time slot (e.g., "10:00 AM")
        """
        t0 = self._tool_start_log(
            "modify_appointment",
            appt_id=appointment_id, new_date=new_date, new_time=new_time
        )

        if not self._user_id:
            log.warning("modify_appointment BLOCKED | session=%s — no user", self._session_id)
            return json.dumps({"success": False, "error": "Patient not identified."})

        await self._emit(
            "tool_start", "modify_appointment",
            f"Rescheduling #{appointment_id} → {new_date} {new_time}..."
        )

        try:
            result = modify_appointment_by_id(self._user_id, appointment_id, new_date.strip(), new_time.strip())
            success = result["success"]
            msg = "Rescheduled" if success else result.get("error", "Error")
            await self._emit("tool_result", "modify_appointment", msg, result)
            self._tool_end_log(
                "modify_appointment", t0, success,
                appt_id=appointment_id, new_date=new_date, new_time=new_time
            )
            return json.dumps(result)
        except Exception as exc:
            log.error(
                "modify_appointment EXCEPTION | session=%s appt_id=%d: %s",
                self._session_id, appointment_id, exc, exc_info=True
            )
            await self._emit("tool_result", "modify_appointment", f"Error: {exc}")
            return json.dumps({"success": False, "error": str(exc)})

    @function_tool
    async def end_conversation(self, summary: str, user_preferences: str = "", intent: str = "") -> str:
        """
        End the conversation and generate a call summary. Call this when the patient is done.

        Args:
            summary: A concise summary of the entire conversation
            user_preferences: Any patient preferences mentioned (optional)
            intent: Primary intent of the call (e.g., "book appointment")
        """
        call_duration_s = time.perf_counter() - self._call_start
        log.info(
            "end_conversation | session=%s user=%r intent=%r tools_called=%d duration=%.1fs",
            self._session_id, self._user_name, intent,
            self._tool_call_count, call_duration_s
        )

        try:
            appointments = get_user_appointments(self._user_id) if self._user_id else []
            active = [a for a in appointments if a["status"] == "booked"]

            save_call_summary(
                session_id=self._session_id,
                user_id=self._user_id,
                phone_number=self._user_phone,
                user_name=self._user_name,
                summary=summary,
                appointments=active,
                preferences=user_preferences,
                intent=intent,
            )

            log.info(
                "CONVERSATION LOG | session=%s | %d turns",
                self._session_id, len(self._transcript),
            )
            for turn in self._transcript:
                log.info(
                    "  [%s] %s: %s",
                    turn["ts"], turn["role"].upper(), turn["text"],
                )

            summary_payload = {
                "session_id": self._session_id,
                "patient_name": self._user_name,
                "phone": self._user_phone,
                "summary": summary,
                "appointments": active,
                "preferences": user_preferences,
                "intent": intent,
                "timestamp": datetime.now().isoformat(),
                "call_duration_seconds": round(call_duration_s),
            }

            await self._emit("summary", "", "Call complete", summary_payload)
            await self._emit("call_ended", "", "Call ended")

            log.info(
                "CALL COMPLETE | session=%s patient=%r phone=%s intent=%r "
                "active_appts=%d tools_called=%d duration=%.0fs",
                self._session_id, self._user_name, self._user_phone,
                intent, len(active), self._tool_call_count, call_duration_s
            )
            return json.dumps({"success": True, "session_id": self._session_id})
        except Exception as exc:
            log.error(
                "end_conversation EXCEPTION | session=%s: %s",
                self._session_id, exc, exc_info=True
            )
            return json.dumps({"success": False, "error": str(exc)})


# ── Entrypoint ────────────────────────────────────────────────────────────────

async def entrypoint(ctx: JobContext):
    log.info("entrypoint | job_id=%s room=%s", ctx.job.id, ctx.room.name)

    try:
        await ctx.connect()
        log.info("Room connected | room=%s participants=%d", ctx.room.name, len(ctx.room.remote_participants))
    except Exception as exc:
        log.critical("Failed to connect to room: %s", exc, exc_info=True)
        return

    agent = HealthcareAgent(ctx)

    groq_key = os.getenv("GROQ_API_KEY", "")
    cartesia_voice = os.getenv("CARTESIA_VOICE_ID", "a0e99841-438c-4a64-b679-ae501e7d6091")

    if not groq_key:
        log.critical("GROQ_API_KEY is not set — LLM will fail")
    if not os.getenv("DEEPGRAM_API_KEY"):
        log.critical("DEEPGRAM_API_KEY is not set — STT will fail")
    if not os.getenv("CARTESIA_API_KEY"):
        log.critical("CARTESIA_API_KEY is not set — TTS will fail")

    log.info(
        "Building AgentSession | llm=llama-3.3-70b@groq stt=deepgram-nova-2 "
        "tts=cartesia voice=%s", cartesia_voice
    )

    groq_client = openai_sdk.AsyncOpenAI(
        base_url="https://api.groq.com/openai/v1",
        api_key=groq_key,
    )
    log.info("Groq client configured | base_url=https://api.groq.com/openai/v1")

    # Build a Cartesia-specific aiohttp session with certifi SSL so the
    # TTS WebSocket connection works on macOS Python.org builds.
    cartesia_ssl = _ssl_module.create_default_context(cafile=certifi.where())
    cartesia_connector = aiohttp.TCPConnector(ssl=cartesia_ssl)
    cartesia_http = aiohttp.ClientSession(connector=cartesia_connector)
    log.info("Cartesia HTTP session created with certifi SSL")

    try:
        session = AgentSession(
            stt=deepgram.STT(model="nova-2", language="en-US"),
            llm=lk_openai.LLM(
                model="llama-3.3-70b-versatile",
                client=groq_client,
            ),
            tts=cartesia.TTS(
                voice=cartesia_voice,
                model="sonic-3.5",
                http_session=cartesia_http,
            ),
        )
        log.info("AgentSession built | session=%s", agent._session_id)
    except Exception as exc:
        log.critical("Failed to build AgentSession: %s", exc, exc_info=True)
        return

    # ── Session event monitors (debug what the pipeline is doing) ────────────
    @session.on("conversation_item_added")
    def on_conversation_item(ev):
        item = ev.item
        if not isinstance(item, ChatMessage):
            return
        role = item.role
        if role not in ("user", "assistant"):
            return
        text = (item.text_content or "").strip()
        if not text:
            return
        ts = datetime.now().isoformat()
        agent._transcript.append({"role": role, "text": text, "ts": ts})
        label = "USER " if role == "user" else "AGENT"
        log.info("CONVO [%s] | session=%s | %s", label, agent._session_id, text)
        asyncio.ensure_future(
            agent._emit("transcript", data={"role": role, "text": text})
        )

    @session.on("close")
    def on_close(ev):
        log.info(
            "SESSION_CLOSE | session=%s turns=%d reason=%s",
            agent._session_id, len(agent._transcript), ev.reason,
        )

    @session.on("error")
    def on_error(ev):
        log.error("SESSION_ERROR | session=%s error=%s", agent._session_id, ev.error)

    try:
        await session.start(agent, room=ctx.room)
        log.info("Session started | session=%s", agent._session_id)

        session.generate_reply(
            instructions="Warmly greet the patient, introduce yourself as Aria from Mykare Health, and ask how you can help them today."
        )
        log.info("Initial greeting triggered | session=%s", agent._session_id)
    except Exception as exc:
        log.error(
            "Session start/greeting failed | session=%s: %s",
            agent._session_id, exc, exc_info=True
        )
        return

    # Keep entrypoint alive until the job shuts down.
    # Without this, entrypoint() returns immediately after session.start(),
    # which kills the background tasks that run the voice pipeline.
    # NOTE: add_shutdown_callback in v1.x requires an async callable.
    shutdown_event = asyncio.Event()

    async def _on_shutdown():
        shutdown_event.set()
        await cartesia_http.close()

    ctx.add_shutdown_callback(_on_shutdown)
    log.info("Waiting for job shutdown | session=%s", agent._session_id)
    await shutdown_event.wait()
    log.info("Job shutting down | session=%s", agent._session_id)


if __name__ == "__main__":
    log.info("Starting LiveKit agent worker | agent_name=mykare-healthcare-agent")
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="mykare-healthcare-agent",
        )
    )
