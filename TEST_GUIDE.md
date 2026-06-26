# Mykare Voice AI — Test Guide

## Prerequisites
- Backend running: `python main.py` (in `backend/`)
- Frontend running: `npm run dev` (in `frontend/`)
- Open: http://localhost:5173

---

## 1. API Health Check

```bash
curl http://localhost:8000/api/health
```
**Expected:**
```json
{"status": "ok", "timestamp": "2026-06-26T22:00:00"}
```

---

## 2. Available Slots

```bash
# Next 7 days
curl http://localhost:8000/api/slots

# Specific date
curl "http://localhost:8000/api/slots?date=2026-06-27"
```
**Expected:** List of dates with available time slots (9 AM–4 PM, Mon–Sat).

---

## 3. Book Appointment (REST)

```bash
curl -X POST http://localhost:8000/api/appointments \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "9876543210",
    "date": "2026-06-28",
    "time_slot": "10:00 AM",
    "notes": "General checkup"
  }'
```
**Expected:**
```json
{"success": true, "appointment_id": 1, "date": "2026-06-28", "time": "10:00 AM"}
```

---

## 4. Double Booking Prevention

Run the same curl from Test 3 again immediately.

**Expected:**
```json
{"detail": "This slot is already booked. Please choose another time."}
```
HTTP status: `409 Conflict`

---

## 5. Retrieve Appointments

```bash
curl http://localhost:8000/api/appointments/9876543210
```
**Expected:** List containing the appointment booked in Test 3.

---

## 6. Cancel Appointment

```bash
curl -X DELETE "http://localhost:8000/api/appointments/1?phone_number=9876543210"
```
**Expected:**
```json
{"success": true, "appointment_id": 1, "message": "Appointment cancelled."}
```

---

## 7. Cancel Already-Cancelled Appointment

Run Test 6 again on the same appointment ID.

**Expected:**
```json
{"detail": "Appointment is already cancelled."}
```

---

## 8. Modify Appointment

```bash
# First book a new one
curl -X POST http://localhost:8000/api/appointments \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "9876543210", "date": "2026-06-28", "time_slot": "2:00 PM"}'

# Then modify it (use the returned appointment_id)
curl -X PUT http://localhost:8000/api/appointments/2 \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "9876543210",
    "appointment_id": 2,
    "new_date": "2026-06-29",
    "new_time": "3:00 PM"
  }'
```
**Expected:**
```json
{"success": true, "appointment_id": 2, "new_date": "2026-06-29", "new_time": "3:00 PM"}
```

---

## 9. Voice Conversation — Book Appointment

**Steps:**
1. Open http://localhost:5173
2. Click **"Start Call with Aria"**
3. Wait for Aria to greet you
4. Speak the following script:

```
You:  "Hi, I'd like to book an appointment"
Aria: [greets, asks for name and phone]
You:  "My name is John and my number is 9876543210"
Aria: [calls identify_user — check Tool Activity tab shows it]
You:  "I want to book for tomorrow"
Aria: [calls fetch_slots — shows available times]
You:  "10 AM works for me"
Aria: [calls book_appointment — shows "Booking confirmed"]
You:  "That's all, thank you"
Aria: [calls end_conversation — summary modal appears]
```

**What to verify:**
- [ ] Tool Activity tab shows each tool as it's called
- [ ] `identify_user` → green checkmark after Aria says your name back
- [ ] `fetch_slots` → shows "Found X day(s)"
- [ ] `book_appointment` → shows "Booked: date at time"
- [ ] Call summary modal appears within 10 seconds of goodbye
- [ ] Summary lists the booked appointment with date + time
- [ ] Avatar mouth moves when Aria speaks

---

## 10. Voice Conversation — Retrieve & Cancel

```
You:  "Hi, I'm calling to check my appointments"
Aria: [asks for name and phone]
You:  "John, 9876543210"
Aria: [calls identify_user]
You:  "What appointments do I have?"
Aria: [calls retrieve_appointments — lists bookings]
You:  "Please cancel appointment number 1"
Aria: [calls cancel_appointment]
You:  "Thanks, bye"
Aria: [calls end_conversation]
```

**What to verify:**
- [ ] Aria reads back the correct appointment details
- [ ] Tool Activity shows `retrieve_appointments` then `cancel_appointment`
- [ ] Summary shows cancelled intent

---

## 11. Voice Conversation — Reschedule

```
You:  "Hi, I want to reschedule my appointment"
Aria: [asks for name and phone]
You:  "9876543210, my name is John"
Aria: [calls identify_user + retrieve_appointments]
You:  "Move appointment 2 to next Monday at 9 AM"
Aria: [calls fetch_slots to confirm, then modify_appointment]
You:  "Perfect, thanks goodbye"
```

**What to verify:**
- [ ] `modify_appointment` appears in Tool Activity
- [ ] Aria confirms the new date and time clearly

---

## 12. Edge Cases

### Unknown phone number (new patient)
```
You: "Hi, my number is 0000000000"
```
**Expected:** Aria registers you as a new patient, confirms "Welcome!"

### Booking a Sunday (no slots available)
```bash
# Find a Sunday date and try booking
curl -X POST http://localhost:8000/api/appointments \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "9876543210", "date": "2026-06-29", "time_slot": "10:00 AM"}'
```
> Note: 2026-06-29 is a Monday — replace with an actual Sunday date.  
> The clinic is closed Sundays so `fetch_slots` will return no slots for that day.

### Book without identifying first (API guard)
During a voice call, if the LLM somehow tries to book before identifying — the tool returns:
```json
{"success": false, "error": "Patient not identified. Please call identify_user first."}
```
Check the logs: `book_appointment BLOCKED` will appear.

### Slot conflict during modify
Try modifying an appointment to a slot already taken — returns:
```json
{"success": false, "error": "The new slot is already taken. Please choose another time."}
```

---

## 13. Call Summary API

```bash
# Replace SESSION_ID with the one shown in the summary modal
curl http://localhost:8000/api/summary/SESSION_ID
```
**Expected:** Full JSON with patient name, phone, summary text, appointments list, intent, timestamp.

---

## 14. Log Verification

Check `backend/logs/mykare.log` after running tests. You should see:

```
TOOL_START [#1] | session=abc123 tool=identify_user
upsert_user NEW_PATIENT | user_id=1 phone=9876543210
TOOL_END | session=abc123 tool=identify_user success=True elapsed=45 ms

TOOL_START [#2] | session=abc123 tool=fetch_slots
fetch_slots | dates_checked=7 dates_with_slots=6 | 8 ms

TOOL_START [#3] | session=abc123 tool=book_appointment
create_appointment SUCCESS | appt_id=1 user_id=1 date=2026-06-28 time=10:00 AM
TOOL_END | session=abc123 tool=book_appointment success=True elapsed=52 ms

CALL COMPLETE | session=abc123 patient='John' intent='book appointment' active_appts=1 tools_called=3 duration=87s
```

---

## 15. Latency Check

| Action | Target | How to measure |
|---|---|---|
| Aria first response | < 3s | Timer starts when call connects |
| Tool call (DB) | < 100ms | Check logs `elapsed=Xms` |
| Full voice round-trip | < 5s | Speak → hear Aria respond |
| Call summary generation | < 10s | Goodbye → summary modal |
