# ErgoCare AI

Voice-enabled ergonomic stress assessment prototype for typed and spoken questionnaire sessions.

## Folder Map

```text
Ergocare AI/
  docs/
    screenshots/          Preview screenshots from browser QA
  public/                 Static browser assets such as favicon
  src/
    data/                 Corrected ErgoCare question bank and category labels
    domain/               Scoring, report, session creation, export, persistence
    styles/               App-wide CSS
    types/                Shared TypeScript types
    ui/                   HTML template rendering for landing, assessment, results
    main.ts               App controller and browser event wiring
```

## Current Prototype Flow

1. User chooses `Type Answers` or `Speak Answers`.
2. App asks all 40 corrected dataset questions.
3. Each answer is stored against its question ID inside one session record.
4. Voice mode can capture a browser audio blob and transcript text per question.
5. App calculates ergonomic risk scores and generates a visual report.
6. User can export the full session JSON.

## Next Backend Folders To Add

```text
server/
  api/                    FastAPI or Node route handlers
  database/               PostgreSQL schema and migrations
  storage/                Audio upload and file storage logic
  ai/                     Speech-to-text, RAG, and report-generation services
```

For now, the frontend stores the latest completed session in browser `localStorage` and supports JSON export.
