import type { AssessmentSession, InputMode } from '../types/assessment'

const LAST_SESSION_KEY = 'ergocare:last-session'

export function createSession(mode: InputMode): AssessmentSession {
  return {
    sessionId: crypto.randomUUID(),
    inputMode: mode,
    createdAt: new Date().toISOString(),
    completedAt: null,
    answers: [],
    scores: null,
    report: null,
  }
}

export function persistSession(session: AssessmentSession): void {
  localStorage.setItem(LAST_SESSION_KEY, JSON.stringify({
    ...session,
    answers: session.answers.map((item) => ({
      ...item,
      audioUrl: item.audioUrl ? '[browser-object-url]' : null,
    })),
  }))
}

export function exportSessionJson(session: AssessmentSession): void {
  const payload = JSON.stringify(session, null, 2)
  const blob = new Blob([payload], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')

  anchor.href = url
  anchor.download = `ergocare-session-${session.sessionId}.json`
  anchor.click()
  URL.revokeObjectURL(url)
}
