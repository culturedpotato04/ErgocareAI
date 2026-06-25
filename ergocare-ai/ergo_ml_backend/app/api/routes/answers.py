"""
Answers route — v3.1
Additions over v3:
  - 10 MB per audio clip hard limit (HTTP 413)
  - File type whitelist: .webm .ogg .mp4 .wav .m4a only (HTTP 415)
  - Disk space guard: refuses upload if < 500 MB free (HTTP 507)
  - Returns clear error messages the frontend can show to the user
"""
import os
import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.assessment import AssessmentSession, AssessmentAnswer, AudioFile
from app.models.schemas import AnswerIn, AnswerOut

router = APIRouter()

AUDIO_DIR        = os.getenv("AUDIO_UPLOAD_DIR", "./uploads/audio")
MAX_AUDIO_BYTES  = int(os.getenv("MAX_AUDIO_MB",  "10"))  * 1024 * 1024   # default 10 MB
MIN_FREE_BYTES   = int(os.getenv("MIN_FREE_MB",  "500")) * 1024 * 1024    # default 500 MB
ALLOWED_TYPES    = {
    "audio/webm", "audio/ogg", "audio/mp4",
    "audio/wav",  "audio/wave", "audio/x-wav",
    "audio/m4a",  "video/webm",                 # Chrome labels .webm as video/webm
}
ALLOWED_EXTS     = {".webm", ".ogg", ".mp4", ".wav", ".m4a"}

os.makedirs(AUDIO_DIR, exist_ok=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_session_or_404(session_id: str, db: Session) -> AssessmentSession:
    session = db.query(AssessmentSession).filter(
        AssessmentSession.id == session_id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


def _check_disk_space():
    """Refuse upload if free disk space is below MIN_FREE_BYTES."""
    try:
        free = shutil.disk_usage(AUDIO_DIR).free
    except Exception:
        return  # can't check — allow and move on
    if free < MIN_FREE_BYTES:
        free_mb  = free  // (1024 * 1024)
        limit_mb = MIN_FREE_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=507,
            detail=(
                f"Server storage critically low ({free_mb} MB free). "
                f"Uploads are paused until at least {limit_mb} MB is available. "
                "Contact the administrator."
            ),
        )


def _check_file_type(file: UploadFile):
    """Reject non-audio MIME types and non-audio file extensions."""
    mime = (file.content_type or "").lower().split(";")[0].strip()
    ext  = os.path.splitext(file.filename or "")[1].lower()

    mime_ok = mime in ALLOWED_TYPES
    ext_ok  = ext  in ALLOWED_EXTS or ext == ""   # ext may be empty for blobs

    if not mime_ok and not ext_ok:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported file type '{mime}' (extension '{ext}'). "
                f"Allowed formats: {', '.join(sorted(ALLOWED_EXTS))}."
            ),
        )


def _check_file_size(data: bytes):
    """Reject files that exceed MAX_AUDIO_BYTES."""
    if len(data) > MAX_AUDIO_BYTES:
        actual_mb = len(data) / (1024 * 1024)
        limit_mb  = MAX_AUDIO_BYTES // (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=(
                f"Audio file too large ({actual_mb:.1f} MB). "
                f"Maximum allowed size is {limit_mb} MB per clip. "
                "Please shorten your recording and try again."
            ),
        )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/{session_id}/answers", response_model=AnswerOut, status_code=201)
def save_answer(
    session_id: str,
    payload:    AnswerIn,
    db:         Session = Depends(get_db),
):
    """
    Save or upsert a single typed/voice answer for one question.
    Called per-question as the user progresses through the assessment.
    """
    _get_session_or_404(session_id, db)

    # Upsert: remove existing answer for the same question
    db.query(AssessmentAnswer).filter(
        AssessmentAnswer.session_id  == session_id,
        AssessmentAnswer.question_id == payload.question_id,
    ).delete()

    answer = AssessmentAnswer(
        session_id    = session_id,
        question_id   = payload.question_id,
        question_text = payload.question_text,
        typed_answer  = payload.typed_answer,
        transcript    = payload.transcript,
        audio_url     = payload.audio_url,
        created_at    = datetime.now(timezone.utc),
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)
    return answer


@router.post("/{session_id}/answers/{question_id}/audio", status_code=201)
async def upload_audio(
    session_id:  str,
    question_id: int,
    file:        UploadFile = File(...),
    transcript:  str        = Form(default=""),
    db:          Session    = Depends(get_db),
):
    """
    Upload a voice recording for one question.

    Limits enforced (all return clear HTTP errors):
      - File type must be audio/webm, ogg, mp4, wav, or m4a  → 415
      - File size must be ≤ MAX_AUDIO_MB (default 10 MB)     → 413
      - Server must have ≥ MIN_FREE_MB disk space free        → 507

    On success:
      - Saves file to  uploads/audio/{session_id}/q{n}_{filename}
      - Updates        assessment_answers row (audio_url + transcript)
      - Inserts        audio_files row for admin playback
    """
    _get_session_or_404(session_id, db)

    # ── Guard 1: file type ────────────────────────────────────────────────────
    _check_file_type(file)

    # ── Guard 2: read into memory so we can size-check before touching disk ──
    data = await file.read()
    _check_file_size(data)

    # ── Guard 3: disk space ───────────────────────────────────────────────────
    _check_disk_space()

    # ── Save to disk ──────────────────────────────────────────────────────────
    session_dir = os.path.join(AUDIO_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)

    raw_name  = file.filename or "recording.webm"
    safe_name = f"q{question_id}_{raw_name}"
    file_path = os.path.join(session_dir, safe_name)

    with open(file_path, "wb") as f:
        f.write(data)

    file_size = len(data)
    audio_url = f"/uploads/audio/{session_id}/{safe_name}"

    # ── Upsert audio_files row ────────────────────────────────────────────────
    db.query(AudioFile).filter(
        AudioFile.session_id  == session_id,
        AudioFile.question_id == question_id,
    ).delete()

    db.add(AudioFile(
        session_id  = session_id,
        question_id = question_id,
        file_name   = safe_name,
        file_path   = file_path,
        mime_type   = file.content_type,
        size_bytes  = file_size,
        created_at  = datetime.now(timezone.utc),
    ))

    # ── Update / create answer row ────────────────────────────────────────────
    existing = db.query(AssessmentAnswer).filter(
        AssessmentAnswer.session_id  == session_id,
        AssessmentAnswer.question_id == question_id,
    ).first()

    if existing:
        existing.audio_url = audio_url
        if transcript:
            existing.transcript = transcript
    else:
        from app.domain.questions import QUESTIONS_BY_ID
        q = QUESTIONS_BY_ID.get(question_id)
        db.add(AssessmentAnswer(
            session_id    = session_id,
            question_id   = question_id,
            question_text = q["text"] if q else f"Question {question_id}",
            transcript    = transcript or None,
            audio_url     = audio_url,
            created_at    = datetime.now(timezone.utc),
        ))

    db.commit()

    limit_mb  = MAX_AUDIO_BYTES // (1024 * 1024)
    actual_mb = round(file_size / (1024 * 1024), 2)

    return {
        "message":   "Audio uploaded successfully",
        "audio_url": audio_url,
        "file_size": file_size,
        "size_mb":   actual_mb,
        "limit_mb":  limit_mb,
    }
