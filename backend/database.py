import sqlite3
import json
import os
import time
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict

from logging_config import get_logger

log = get_logger(__name__)

DB_PATH = os.getenv("DB_PATH", "mykare.db")


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    log.info("Initialising database at %s", DB_PATH)
    t0 = time.perf_counter()
    try:
        conn = get_db()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone_number TEXT UNIQUE NOT NULL,
                name TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS appointments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                status TEXT DEFAULT 'booked',
                notes TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS call_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                user_id INTEGER,
                phone_number TEXT,
                user_name TEXT,
                summary TEXT,
                appointments_json TEXT DEFAULT '[]',
                preferences TEXT DEFAULT '',
                intent TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
        """)
        conn.commit()
        conn.close()
        log.info("Database ready (%.1f ms)", (time.perf_counter() - t0) * 1000)
    except sqlite3.Error as exc:
        log.critical("Failed to initialise database: %s", exc, exc_info=True)
        raise


# Available time slots (hardcoded business hours)
AVAILABLE_TIMES = ["9:00 AM", "10:00 AM", "11:00 AM", "2:00 PM", "3:00 PM", "4:00 PM"]


def get_available_slots(target_date: Optional[str] = None) -> List[Dict]:
    log.debug("get_available_slots called | target_date=%s", target_date or "next-7-days")
    t0 = time.perf_counter()
    conn = get_db()
    results = []
    dates_to_check: List[str] = []

    if target_date:
        dates_to_check = [target_date]
    else:
        today = date.today()
        for i in range(1, 8):
            d = today + timedelta(days=i)
            if d.weekday() != 6:  # skip Sunday
                dates_to_check.append(d.strftime("%Y-%m-%d"))

    for slot_date in dates_to_check:
        try:
            booked_times = conn.execute(
                "SELECT time_slot FROM appointments WHERE date=? AND status='booked'",
                (slot_date,)
            ).fetchall()
            booked_set = {r["time_slot"] for r in booked_times}
            available = [t for t in AVAILABLE_TIMES if t not in booked_set]
            if available:
                results.append({"date": slot_date, "available_times": available})
            log.debug(
                "  %s — booked=%d available=%d",
                slot_date, len(booked_set), len(available)
            )
        except sqlite3.Error as exc:
            log.error("DB error querying slots for %s: %s", slot_date, exc, exc_info=True)

    conn.close()
    log.info(
        "fetch_slots | dates_checked=%d dates_with_slots=%d | %.1f ms",
        len(dates_to_check), len(results), (time.perf_counter() - t0) * 1000
    )
    return results


def upsert_user(phone_number: str, name: str = "") -> Dict:
    log.debug("upsert_user | phone=%s name=%r", phone_number, name)
    t0 = time.perf_counter()
    try:
        conn = get_db()
        existing = conn.execute(
            "SELECT * FROM users WHERE phone_number=?", (phone_number,)
        ).fetchone()

        if existing:
            if name and not existing["name"]:
                conn.execute(
                    "UPDATE users SET name=? WHERE phone_number=?", (name, phone_number)
                )
                conn.commit()
                log.debug("  Updated name for existing user phone=%s", phone_number)
            user = conn.execute(
                "SELECT * FROM users WHERE phone_number=?", (phone_number,)
            ).fetchone()
            conn.close()
            result = {
                "user_id": user["id"],
                "name": user["name"] or name,
                "phone": phone_number,
                "is_new": False,
            }
            log.info(
                "upsert_user RETURNING_PATIENT | user_id=%d phone=%s name=%r | %.1f ms",
                result["user_id"], phone_number, result["name"],
                (time.perf_counter() - t0) * 1000
            )
            return result
        else:
            cursor = conn.execute(
                "INSERT INTO users (phone_number, name) VALUES (?, ?)", (phone_number, name)
            )
            conn.commit()
            user_id = cursor.lastrowid
            conn.close()
            result = {"user_id": user_id, "name": name, "phone": phone_number, "is_new": True}
            log.info(
                "upsert_user NEW_PATIENT | user_id=%d phone=%s name=%r | %.1f ms",
                user_id, phone_number, name,
                (time.perf_counter() - t0) * 1000
            )
            return result
    except sqlite3.Error as exc:
        log.error("upsert_user DB error | phone=%s: %s", phone_number, exc, exc_info=True)
        raise


def create_appointment(user_id: int, slot_date: str, time_slot: str, notes: str = "") -> Dict:
    log.debug(
        "create_appointment | user_id=%d date=%s time=%s notes=%r",
        user_id, slot_date, time_slot, notes
    )
    t0 = time.perf_counter()
    try:
        conn = get_db()

        # Double-booking check
        existing = conn.execute(
            "SELECT id FROM appointments WHERE date=? AND time_slot=? AND status='booked'",
            (slot_date, time_slot)
        ).fetchone()

        if existing:
            conn.close()
            log.warning(
                "create_appointment DOUBLE_BOOK blocked | date=%s time=%s | existing_appt_id=%d",
                slot_date, time_slot, existing["id"]
            )
            return {"success": False, "error": "This slot is already booked. Please choose another time."}

        cursor = conn.execute(
            "INSERT INTO appointments (user_id, date, time_slot, notes) VALUES (?, ?, ?, ?)",
            (user_id, slot_date, time_slot, notes)
        )
        conn.commit()
        appt_id = cursor.lastrowid
        conn.close()
        log.info(
            "create_appointment SUCCESS | appt_id=%d user_id=%d date=%s time=%s | %.1f ms",
            appt_id, user_id, slot_date, time_slot,
            (time.perf_counter() - t0) * 1000
        )
        return {"success": True, "appointment_id": appt_id, "date": slot_date, "time": time_slot}
    except sqlite3.Error as exc:
        log.error(
            "create_appointment DB error | user_id=%d date=%s time=%s: %s",
            user_id, slot_date, time_slot, exc, exc_info=True
        )
        raise


def get_user_appointments(user_id: int) -> List[Dict]:
    log.debug("get_user_appointments | user_id=%d", user_id)
    t0 = time.perf_counter()
    try:
        conn = get_db()
        rows = conn.execute(
            """SELECT a.id, a.date, a.time_slot, a.status, a.notes, a.created_at
               FROM appointments a WHERE a.user_id=? ORDER BY a.date ASC, a.time_slot ASC""",
            (user_id,)
        ).fetchall()
        conn.close()
        result = [dict(r) for r in rows]
        active = sum(1 for r in result if r["status"] == "booked")
        log.info(
            "get_user_appointments | user_id=%d total=%d active=%d | %.1f ms",
            user_id, len(result), active,
            (time.perf_counter() - t0) * 1000
        )
        return result
    except sqlite3.Error as exc:
        log.error("get_user_appointments DB error | user_id=%d: %s", user_id, exc, exc_info=True)
        raise


def cancel_appointment_by_id(appointment_id: int, user_id: int) -> Dict:
    log.debug("cancel_appointment | appt_id=%d user_id=%d", appointment_id, user_id)
    t0 = time.perf_counter()
    try:
        conn = get_db()
        appt = conn.execute(
            "SELECT * FROM appointments WHERE id=? AND user_id=?", (appointment_id, user_id)
        ).fetchone()

        if not appt:
            conn.close()
            log.warning(
                "cancel_appointment NOT_FOUND | appt_id=%d user_id=%d",
                appointment_id, user_id
            )
            return {"success": False, "error": "Appointment not found."}

        if appt["status"] == "cancelled":
            conn.close()
            log.warning(
                "cancel_appointment ALREADY_CANCELLED | appt_id=%d user_id=%d",
                appointment_id, user_id
            )
            return {"success": False, "error": "Appointment is already cancelled."}

        conn.execute(
            "UPDATE appointments SET status='cancelled' WHERE id=?", (appointment_id,)
        )
        conn.commit()
        conn.close()
        log.info(
            "cancel_appointment SUCCESS | appt_id=%d user_id=%d was_date=%s was_time=%s | %.1f ms",
            appointment_id, user_id, appt["date"], appt["time_slot"],
            (time.perf_counter() - t0) * 1000
        )
        return {"success": True, "appointment_id": appointment_id, "message": "Appointment cancelled."}
    except sqlite3.Error as exc:
        log.error(
            "cancel_appointment DB error | appt_id=%d user_id=%d: %s",
            appointment_id, user_id, exc, exc_info=True
        )
        raise


def modify_appointment_by_id(appointment_id: int, user_id: int, new_date: str, new_time: str) -> Dict:
    log.debug(
        "modify_appointment | appt_id=%d user_id=%d new_date=%s new_time=%s",
        appointment_id, user_id, new_date, new_time
    )
    t0 = time.perf_counter()
    try:
        conn = get_db()
        appt = conn.execute(
            "SELECT * FROM appointments WHERE id=? AND user_id=? AND status='booked'",
            (appointment_id, user_id)
        ).fetchone()

        if not appt:
            conn.close()
            log.warning(
                "modify_appointment NOT_FOUND | appt_id=%d user_id=%d",
                appointment_id, user_id
            )
            return {"success": False, "error": "Active appointment not found."}

        conflict = conn.execute(
            "SELECT id FROM appointments WHERE date=? AND time_slot=? AND status='booked' AND id!=?",
            (new_date, new_time, appointment_id)
        ).fetchone()

        if conflict:
            conn.close()
            log.warning(
                "modify_appointment CONFLICT | appt_id=%d -> %s %s already taken by appt_id=%d",
                appointment_id, new_date, new_time, conflict["id"]
            )
            return {"success": False, "error": "The new slot is already taken. Please choose another time."}

        conn.execute(
            "UPDATE appointments SET date=?, time_slot=? WHERE id=?",
            (new_date, new_time, appointment_id)
        )
        conn.commit()
        conn.close()
        log.info(
            "modify_appointment SUCCESS | appt_id=%d user_id=%d | %s %s -> %s %s | %.1f ms",
            appointment_id, user_id,
            appt["date"], appt["time_slot"], new_date, new_time,
            (time.perf_counter() - t0) * 1000
        )
        return {
            "success": True,
            "appointment_id": appointment_id,
            "new_date": new_date,
            "new_time": new_time,
            "message": "Appointment rescheduled.",
        }
    except sqlite3.Error as exc:
        log.error(
            "modify_appointment DB error | appt_id=%d user_id=%d: %s",
            appointment_id, user_id, exc, exc_info=True
        )
        raise


def save_call_summary(
    session_id: str,
    user_id: Optional[int],
    phone_number: str,
    user_name: str,
    summary: str,
    appointments: List[Dict],
    preferences: str = "",
    intent: str = "",
) -> Dict:
    log.debug(
        "save_call_summary | session=%s user_id=%s phone=%s appts=%d",
        session_id, user_id, phone_number, len(appointments)
    )
    t0 = time.perf_counter()
    try:
        conn = get_db()
        conn.execute(
            """INSERT OR REPLACE INTO call_summaries
               (session_id, user_id, phone_number, user_name, summary,
                appointments_json, preferences, intent)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, user_id, phone_number, user_name, summary,
             json.dumps(appointments), preferences, intent)
        )
        conn.commit()
        conn.close()
        log.info(
            "save_call_summary SUCCESS | session=%s user=%r intent=%r summary_len=%d appts=%d | %.1f ms",
            session_id, user_name, intent, len(summary), len(appointments),
            (time.perf_counter() - t0) * 1000
        )
        return {"success": True, "session_id": session_id}
    except sqlite3.Error as exc:
        log.error(
            "save_call_summary DB error | session=%s: %s", session_id, exc, exc_info=True
        )
        raise


def get_call_summary(session_id: str) -> Optional[Dict]:
    log.debug("get_call_summary | session=%s", session_id)
    t0 = time.perf_counter()
    try:
        conn = get_db()
        row = conn.execute(
            "SELECT * FROM call_summaries WHERE session_id=?", (session_id,)
        ).fetchone()
        conn.close()
        if not row:
            log.warning("get_call_summary NOT_FOUND | session=%s", session_id)
            return None
        result = dict(row)
        result["appointments"] = json.loads(result.get("appointments_json", "[]"))
        log.info(
            "get_call_summary FOUND | session=%s user=%r | %.1f ms",
            session_id, result.get("user_name"),
            (time.perf_counter() - t0) * 1000
        )
        return result
    except sqlite3.Error as exc:
        log.error("get_call_summary DB error | session=%s: %s", session_id, exc, exc_info=True)
        raise
