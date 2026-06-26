# Mykare Voice AI — Healthcare Front-Desk Agent

A real-world AI voice agent for healthcare appointment management. Talk to Aria (the AI receptionist) using your microphone to book, manage, and cancel appointments.

## Architecture

```
Frontend (React + Vite)        Backend (Python + FastAPI)
┌──────────────────────┐       ┌────────────────────────────┐
│  LiveKit Room UI     │◄─────►│  FastAPI REST API (:8000)  │
│  Animated Avatar     │       │  SQLite Database            │
│  Tool Call Display   │       └──────────┬─────────────────┘
│  Transcript Panel    │                  │
│  Call Summary Modal  │       ┌──────────▼─────────────────┐
└──────────┬───────────┘       │  LiveKit Agent Worker       │
           │                   │  • Deepgram STT             │
           └──────LiveKit──────│  • Cartesia TTS             │
                WebRTC         │  • OpenAI GPT-4o-mini LLM   │
                               │  • 7 Tool Functions         │
                               └────────────────────────────┘
```

## Prerequisites

Sign up for these services (all have free tiers):
- **LiveKit Cloud**: https://cloud.livekit.io (free tier)
- **Deepgram**: https://deepgram.com ($200 free credit)
- **Cartesia**: https://cartesia.ai (free trial)
- **OpenAI**: https://platform.openai.com

## Setup

### Backend

```bash
cd backend
cp .env.example .env
# Fill in your API keys in .env

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Single command starts both API + Agent worker
python main.py
```
6405617031

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173

## Features

| Feature | Description |
|---|---|
| Voice conversation | Deepgram STT + Cartesia TTS via LiveKit WebRTC |
| Animated avatar | Mouth syncs with agent's speech volume |
| Tool calling | 7 tools with real-time visual feedback |
| Appointment DB | SQLite with double-booking prevention |
| Call summary | Auto-generated at call end, shown on UI |
| Transcript | Live conversation transcript |

## Tools

| Tool | Action |
|---|---|
| `identify_user` | Register/lookup patient by phone number |
| `fetch_slots` | Get available appointment slots (next 7 days) |
| `book_appointment` | Book a slot (prevents double-booking) |
| `retrieve_appointments` | List patient's existing appointments |
| `cancel_appointment` | Cancel a booking |
| `modify_appointment` | Reschedule to a new slot |
| `end_conversation` | Generate and save call summary |

## API Endpoints

```
GET  /api/health                    Health check
POST /api/start-call                Create room + dispatch agent
GET  /api/slots?date=YYYY-MM-DD     Available slots
GET  /api/appointments/{phone}      Patient's appointments
POST /api/appointments              Book appointment
PUT  /api/appointments/{id}         Modify appointment
DELETE /api/appointments/{id}       Cancel appointment
POST /api/summary                   Save call summary
GET  /api/summary/{session_id}      Get call summary
```

## Cost Per Call (Approximate)

| Service | Rate | Per 5-min call |
|---|---|---|
| Deepgram Nova-2 | $0.0043/min | ~$0.022 |
| Cartesia Sonic | $0.01/min | ~$0.05 |
| OpenAI GPT-4o-mini | ~$0.0002/1K tokens | ~$0.01 |
| LiveKit Cloud | $0.006/min/participant | ~$0.06 |
| **Total** | | **~$0.14 / call** |

## Environment Variables

```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret
DEEPGRAM_API_KEY=your_deepgram_api_key
CARTESIA_API_KEY=your_cartesia_api_key
CARTESIA_VOICE_ID=a0e99841-438c-4a64-b679-ae501e7d6091
OPENAI_API_KEY=your_openai_api_key
DB_PATH=mykare.db
API_PORT=8000
FRONTEND_URL=http://localhost:5173
```
