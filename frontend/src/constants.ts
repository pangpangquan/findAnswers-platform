import type { AnswerSource, QuestionType, TaskStatus, TaskItem } from './types'

export const LOW_CONFIDENCE_THRESHOLD = 0.6

export const QUESTION_TYPE_LABELS: Record<QuestionType, string> = {
  eight_legged: '八股',
  handwritten_code: '手撕代码',
  scenario: '场景设计',
  project: '项目深挖',
}

export const QUESTION_TYPE_OPTIONS = Object.entries(QUESTION_TYPE_LABELS).map(([value, label]) => ({
  value,
  label,
}))

export const ANSWER_SOURCE_META: Record<AnswerSource, { label: string; color: string }> = {
  original: { label: '来自原帖', color: 'green' },
  ai: { label: 'AI 生成', color: 'orange' },
}

export const ANSWER_SOURCE_OPTIONS = Object.entries(ANSWER_SOURCE_META).map(([value, m]) => ({
  value,
  label: m.label,
}))

export const TASK_STATUS_META: Record<TaskStatus, { label: string; color: string }> = {
  pending: { label: '排队中', color: 'default' },
  processing: { label: '处理中', color: 'processing' },
  done: { label: '完成', color: 'success' },
  done_with_warnings: { label: '完成·低置信度', color: 'warning' },
  failed: { label: '失败', color: 'error' },
}

export const TASK_TYPE_LABELS: Record<TaskItem['task_type'], string> = {
  manual_images: '手动上传',
  xhs: '小红书',
  niuke: '牛客',
}
