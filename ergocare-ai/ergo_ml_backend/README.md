# ErgoCare AI Backend — v3

FastAPI backend. Drop-in replacement for the existing `ergocare-backend/` folder.

## What changed in v3

| Feature | Before | Now |
|---|---|---|
| Client info stored | ❌ | ✅ name, email, phone, age, job saved per session |
| Admin list endpoint | ❌ | ✅ `GET /api/sessions/admin` (X-Admin-Token required) |
| Delete session | ❌ | ✅ `DELETE /api/sessions/{id}` (X-Admin-Token required) |
| Audio served | ❌ | ✅ `/uploads/audio/{session_id}/{file}` via StaticFiles |
| Audio list | ❌ | ✅ `GET /api/sessions/{id}/audio` |
| PDF has client info | ❌ | ✅ name, email, phone, age, job, session ID |
| PDF has all 40 answers | ❌ | ✅ every Q&A + audio notation |

## Quick start

```bash
cd ergocare-backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## Key endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/api/sessions` | — | Create session (sends client_* fields) |
| GET | `/api/sessions/admin` | X-Admin-Token | All sessions with client info |
| DELETE | `/api/sessions/{id}` | X-Admin-Token | Delete session + audio from disk |
| POST | `/api/sessions/{id}/answers` | — | Save one answer |
| POST | `/api/sessions/{id}/answers/{qid}/audio` | — | Upload voice clip |
| GET | `/api/sessions/{id}/audio` | — | List audio files |
| POST | `/api/sessions/{id}/complete` | — | Score + build report |
| GET | `/api/sessions/{id}/report` | — | Full JSON report + answers |
| GET | `/api/sessions/{id}/report.pdf` | — | PDF download |

## Admin token

Set `ADMIN_TOKEN` env var (default: `ergocare-admin-2026`).  
Must match `ADMIN_TOKEN` constant in `index.html` line ~1501.

## Files changed

```
ergocare-backend/
  app/
    main.py                  ← mounts /uploads/audio, v3 description
    models/
      assessment.py          ← added client_name/email/phone/age/job columns
      schemas.py             ← SessionCreate accepts client_* fields; AudioFileOut added; SessionOut includes client fields
    api/routes/
      sessions.py            ← GET /admin, DELETE /{id}, GET /{id}/audio
      answers.py             ← unchanged logic (audio upload improved)
      reports.py             ← PDF now includes client info + all 40 answers
```

## ⚠ Database migration

If you already have a database (`ergocare.db`), the new `client_*` columns won't exist.
**Two options:**

**Option A — Delete and recreate (recommended for dev):**
```bash
rm ergocare-backend/ergocare.db
uvicorn app.main:app --reload --port 8000
# Tables are auto-created on startup
```

**Option B — Run migration SQL:**
```sql
ALTER TABLE assessment_sessions ADD COLUMN client_name TEXT;
ALTER TABLE assessment_sessions ADD COLUMN client_email TEXT;
ALTER TABLE assessment_sessions ADD COLUMN client_phone TEXT;
ALTER TABLE assessment_sessions ADD COLUMN client_age INTEGER;
ALTER TABLE assessment_sessions ADD COLUMN client_job TEXT;
```
