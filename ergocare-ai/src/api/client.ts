// ─── ErgoCare AI — Backend API Client ────────────────────────────────────────
// Drop this file into src/api/client.ts
// Every call to the FastAPI backend goes through here.

export const API_BASE = 'http://127.0.0.1:8000'

// ── Types returned by the backend ────────────────────────────────────────────

export type BackendSession = {
  id: string
  input_mode: string
  created_at: string
  completed_at: string | null
  overall_risk: number | null
  posture_risk: number | null
  eye_strain: number | null
  workload_stress: number | null
  musculoskeletal_risk: number | null
  recovery_risk: number | null
  report_json: BackendReport | null
  answers: BackendAnswer[]
}

export type BackendAnswer = {
  id: number
  session_id: string
  question_id: number
  question_text: string
  typed_answer: string | null
  transcript: string | null
  audio_url: string | null
  created_at: string
}

export type BackendScores = {
  posture_risk: number
  eye_strain: number
  workload_stress: number
  musculoskeletal_risk: number
  recovery_risk: number
  overall_risk: number
}

export type BackendReport = {
  level: 'Low' | 'Moderate' | 'High'
  top_factors: string[]
  action_plan: string[]
  category_breakdown: Record<string, number>
  detailed_findings: string[]
  positive_habits: string[]
}

export type CompleteSessionResponse = {
  session_id: string
  scores: BackendScores
  report: BackendReport
}

// ── Helpers ───────────────────────────────────────────────────────────────────

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`API ${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

// ── Session ───────────────────────────────────────────────────────────────────

export async function apiCreateSession(inputMode: 'typed' | 'voice'): Promise<BackendSession> {
  return request<BackendSession>('/api/sessions', {
    method: 'POST',
    body: JSON.stringify({ input_mode: inputMode }),
  })
}

export async function apiGetSession(sessionId: string): Promise<BackendSession> {
  return request<BackendSession>(`/api/sessions/${sessionId}`)
}

// ── Answers ───────────────────────────────────────────────────────────────────

export async function apiSaveAnswer(
  sessionId: string,
  questionId: number,
  questionText: string,
  typedAnswer: string | null,
  transcript: string | null,
  audioUrl: string | null,
): Promise<BackendAnswer> {
  return request<BackendAnswer>(`/api/sessions/${sessionId}/answers`, {
    method: 'POST',
    body: JSON.stringify({
      question_id: questionId,
      question_text: questionText,
      typed_answer: typedAnswer,
      transcript,
      audio_url: audioUrl,
    }),
  })
}

export async function apiUploadAudio(
  sessionId: string,
  questionId: number,
  audioBlob: Blob,
  fileName: string,
  transcript: string,
): Promise<{ audio_url: string; file_size: number }> {
  const form = new FormData()
  form.append('file', audioBlob, fileName)
  form.append('transcript', transcript)

  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/answers/${questionId}/audio`, {
    method: 'POST',
    body: form,
    // Do NOT set Content-Type — browser sets it with boundary automatically
  })
  if (!res.ok) {
    const detail = await res.text()
    throw new Error(`Audio upload ${res.status}: ${detail}`)
  }
  return res.json()
}

// ── Complete & Report ─────────────────────────────────────────────────────────

export async function apiCompleteSession(sessionId: string): Promise<CompleteSessionResponse> {
  return request<CompleteSessionResponse>(`/api/sessions/${sessionId}/complete`, {
    method: 'POST',
  })
}

export function apiReportPdfUrl(sessionId: string): string {
  return `${API_BASE}/api/sessions/${sessionId}/report.pdf`
}
