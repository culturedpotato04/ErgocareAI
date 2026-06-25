export type InputMode = 'typed' | 'voice'
export type Screen = 'landing' | 'assessment' | 'results'

export type QuestionCategory =
  | 'workload'
  | 'eyes'
  | 'posture'
  | 'movement'
  | 'recovery'
  | 'pain'

export type Question = {
  id: number
  text: string
  options: string[]
  category: QuestionCategory
  reverse?: boolean
  riskMap?: Record<string, number>
}

export type AnswerRecord = {
  questionId: number
  question: string
  typedAnswer: string | null
  transcript: string | null
  audioUrl: string | null
  audioFileName: string | null
}

export type AssessmentSession = {
  sessionId: string
  inputMode: InputMode
  createdAt: string
  completedAt: string | null
  answers: AnswerRecord[]
  scores: RiskScores | null
  report: ReportData | null
}

export type RiskScores = {
  postureRisk: number
  eyeStrain: number
  workloadStress: number
  musculoskeletalRisk: number
  recoveryRisk: number
  overallRisk: number
}

export type ReportData = {
  level: 'Low' | 'Moderate' | 'High'
  topFactors: string[]
  actionPlan: string[]
}

export type RecognitionLike = {
  continuous: boolean
  interimResults: boolean
  lang: string
  start: () => void
  stop: () => void
  onresult: ((event: SpeechRecognitionEventLike) => void) | null
  onend: (() => void) | null
}

export type SpeechRecognitionEventLike = {
  results: ArrayLike<{
    isFinal: boolean
    0: { transcript: string }
  }>
}
