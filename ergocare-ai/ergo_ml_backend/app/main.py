"""
ErgoCare AI Backend — v3
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from app.db.database import create_db_tables
from app.api.routes import sessions, answers, reports

AUDIO_DIR = os.getenv("AUDIO_UPLOAD_DIR", "./uploads/audio")
os.makedirs(AUDIO_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_tables()
    yield


app = FastAPI(
    title="ErgoCare AI Backend",
    description=(
        "Backend for ErgoCare AI ergonomic assessment.\n\n"
        "**v3 additions:**\n"
        "- Client registration fields (name, email, phone, age, job) stored per session\n"
        "- `GET /api/sessions/admin` — admin list with all client data (X-Admin-Token required)\n"
        "- `DELETE /api/sessions/{id}` — delete session + audio files from disk (X-Admin-Token required)\n"
        "- `GET /api/sessions/{id}/audio` — list audio clips for a session\n"
        "- PDF includes client info, all 40 Q&A answers, and audio notation\n"
        "- Audio files served at `/uploads/audio/{session_id}/{filename}`\n"
    ),
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])
app.include_router(answers.router,  prefix="/api/sessions", tags=["Answers"])
app.include_router(reports.router,  prefix="/api/sessions", tags=["Reports"])

# Serve audio files directly — admin panel plays them via <audio src="...">
app.mount("/uploads/audio", StaticFiles(directory=AUDIO_DIR), name="audio")


@app.get("/")
def root():
    return {
        "message": "ErgoCare AI API v3 is running",
        "docs":    "/docs",
        "admin_endpoint": "GET /api/sessions/admin  (requires X-Admin-Token header)",
    }

@app.get("/health")
def health():
    return {"status": "ok", "version": "3.0.0"}
