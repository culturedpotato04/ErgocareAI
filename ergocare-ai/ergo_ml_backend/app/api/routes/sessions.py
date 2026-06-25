"""
Sessions route — v3
New endpoints:
  GET  /api/sessions/admin          → admin list with client info + scores (X-Admin-Token required)
  DELETE /api/sessions/{id}         → delete session + all answers + audio files (X-Admin-Token required)
  GET  /api/sessions/{id}/audio     → list all audio files for a session
"""
import os, shutil
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Optional

from app.db.database import get_db
from app.models.assessment import AssessmentSession, AudioFile
from app.models.schemas import SessionCreate, SessionOut
import uuid

router = APIRouter()

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "ergocare-admin-2026")   # match index.html
AUDIO_DIR   = os.getenv("AUDIO_UPLOAD_DIR", "./uploads/audio")


def _require_admin(x_admin_token: Optional[str] = Header(default=None)):
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid or missing admin token")


# ── Create session ────────────────────────────────────────────────────────────

@router.post("", response_model=SessionOut, status_code=201)
def create_session(payload: SessionCreate, db: Session = Depends(get_db)):
    """
    Create a new assessment session.
    Accepts optional client_* fields from the registration form in index.html.
    """
    if payload.input_mode not in ("typed", "voice"):
        raise HTTPException(status_code=422, detail="input_mode must be 'typed' or 'voice'")

    session = AssessmentSession(
        id=str(uuid.uuid4()),
        input_mode=payload.input_mode,
        created_at=datetime.now(timezone.utc),
        client_name=payload.client_name,
        client_email=payload.client_email,
        client_phone=payload.client_phone,
        client_age=payload.client_age,
        client_job=payload.client_job,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


# ── Admin: list all sessions with client info ─────────────────────────────────

@router.get("/admin", response_model=list[SessionOut])
def admin_list_sessions(
    db: Session = Depends(get_db),
    x_admin_token: Optional[str] = Header(default=None),
):
    """
    Return ALL sessions (most recent first) including client details and scores.
    Requires X-Admin-Token header matching ADMIN_TOKEN env var.
    Frontend fetches this at GET /api/sessions/admin.
    """
    _require_admin(x_admin_token)
    return (
        db.query(AssessmentSession)
        .order_by(AssessmentSession.created_at.desc())
        .all()
    )


# ── Get single session ────────────────────────────────────────────────────────

@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: str, db: Session = Depends(get_db)):
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


# ── List all (no client data — public) ───────────────────────────────────────

@router.get("", response_model=list[SessionOut])
def list_sessions(db: Session = Depends(get_db)):
    return db.query(AssessmentSession).order_by(AssessmentSession.created_at.desc()).all()


# ── Delete session (admin only) ───────────────────────────────────────────────

@router.delete("/{session_id}", status_code=204)
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    x_admin_token: Optional[str] = Header(default=None),
):
    """
    Permanently delete a session, all its answers, and all audio files from disk.
    Requires X-Admin-Token. Called by index.html deleteClient().
    """
    _require_admin(x_admin_token)
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Remove audio files from disk
    session_audio_dir = os.path.join(AUDIO_DIR, session_id)
    if os.path.isdir(session_audio_dir):
        shutil.rmtree(session_audio_dir, ignore_errors=True)

    db.delete(session)   # cascades to answers + audio_files rows
    db.commit()
    return


# ── List audio files for a session ───────────────────────────────────────────

@router.get("/{session_id}/audio")
def list_audio_files(session_id: str, db: Session = Depends(get_db)):
    """
    Return all audio clips recorded for a session.
    Each entry includes audio_url so the admin panel can play them back.
    """
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return [
        {
            "question_id": af.question_id,
            "file_name":   af.file_name,
            "audio_url":   f"/uploads/audio/{session_id}/{af.file_name}",
            "mime_type":   af.mime_type,
            "size_bytes":  af.size_bytes,
            "created_at":  af.created_at,
        }
        for af in session.audio_files
    ]
