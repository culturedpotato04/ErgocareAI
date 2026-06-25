import { questions } from '../data/questions'
import type { AnswerRecord, Question, RiskScores, ReportData } from '../types/assessment'

export function optionRisk(question: Question, answer: string): number {
  const normalized = answer.trim().toLowerCase()

  const mappedRisk = Object.entries(question.riskMap ?? {}).find(([option]) => option.toLowerCase() === normalized)
  if (mappedRisk) return mappedRisk[1]

  if (['yes'].includes(normalized)) return 100
  if (['maybe', 'somewhat'].includes(normalized)) return 55
  if (['no'].includes(normalized)) return 0

  const numeric = Number.parseInt(normalized, 10)
  const numericScale = question.options.every((option) => !Number.isNaN(Number.parseInt(option, 10)))
  if (!Number.isNaN(numeric) && numericScale) return Math.round((numeric / 5) * 100)

  const index = question.options.findIndex((option) => option.toLowerCase() === normalized)
  if (index === -1) return 50

  const denominator = Math.max(question.options.length - 1, 1)
  const raw = Math.round((index / denominator) * 100)
  return question.reverse ? 100 - raw : raw
}

export function calculateScores(answers: AnswerRecord[]): RiskScores {
  const byCategory = new Map<Question['category'], number[]>()

  answers.forEach((answer) => {
    const question = questions.find((item) => item.id === answer.questionId)
    if (!question) return

    const value = answer.typedAnswer ?? answer.transcript ?? ''
    const bucket = byCategory.get(question.category) ?? []
    bucket.push(optionRisk(question, value))
    byCategory.set(question.category, bucket)
  })

  const average = (category: Question['category']): number => {
    const values = byCategory.get(category) ?? []
    if (!values.length) return 0
    return Math.round(values.reduce((sum, value) => sum + value, 0) / values.length)
  }

  const postureRisk = Math.round((average('posture') * 0.7) + (average('movement') * 0.3))
  const eyeStrain = average('eyes')
  const workloadStress = average('workload')
  const musculoskeletalRisk = average('pain')
  const recoveryRisk = average('recovery')
  const overallRisk = Math.round(
    postureRisk * 0.2 +
      eyeStrain * 0.18 +
      workloadStress * 0.2 +
      musculoskeletalRisk * 0.27 +
      recoveryRisk * 0.15,
  )

  return {
    postureRisk,
    eyeStrain,
    workloadStress,
    musculoskeletalRisk,
    recoveryRisk,
    overallRisk,
  }
}

export function buildReport(scores: RiskScores, answers: AnswerRecord[]): ReportData {
  const level = scores.overallRisk >= 70 ? 'High' : scores.overallRisk >= 40 ? 'Moderate' : 'Low'
  const factors = [
    ['Body discomfort', scores.musculoskeletalRisk],
    ['Workload pressure', scores.workloadStress],
    ['Posture setup', scores.postureRisk],
    ['Eye strain', scores.eyeStrain],
    ['Recovery and sleep', scores.recoveryRisk],
  ]
    .sort((a, b) => Number(b[1]) - Number(a[1]))
    .slice(0, 3)
    .map(([label, value]) => `${label}: ${value}%`)

  const highPainAnswers = answers
    .filter((answer) => {
      const question = questions.find((item) => item.id === answer.questionId)
      return question?.category === 'pain' && optionRisk(question, answer.typedAnswer ?? answer.transcript ?? '') >= 70
    })
    .slice(0, 2)
    .map((answer) => answer.question)

  const actionPlan = [
    'Use a 25-5 or 50-10 work rhythm and record breaks as part of the daily routine.',
    'Raise the screen to eye level and keep external keyboard or mouse support for long laptop sessions.',
    'Add two micro-stretch blocks focused on neck, shoulders, lower back, and wrists.',
    'Reduce screen fatigue with lighting correction, blink breaks, and phone-use boundaries during work.',
    'If radiating pain, numbness, severe headaches, or persistent symptoms continue, consult a qualified clinician.',
  ]

  if (highPainAnswers.length) {
    actionPlan.unshift(`Priority discomfort signals: ${highPainAnswers.join('; ')}`)
  }

  return {
    level,
    topFactors: factors,
    actionPlan,
  }
}
