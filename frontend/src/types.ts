export type QuestionType = 'eight_legged' | 'handwritten_code' | 'scenario' | 'project'
export type AnswerSource = 'original' | 'ai'
export type TaskStatus = 'pending' | 'processing' | 'done' | 'done_with_warnings' | 'failed'

export interface TaskItem {
  id: number
  post_id: number
  task_type: 'manual_images' | 'xhs' | 'niuke'
  status: TaskStatus
  retry_count: number
  error_message: string | null
  stage_stats: Record<string, number> | null
  created_at: string
  finished_at: string | null
}

export interface Question {
  id: number
  post_id: number
  image_id: number | null
  content: string
  question_type: QuestionType
  answer_markdown: string | null
  answer_source: AnswerSource
  company: string | null
  direction: string | null
  interview_round: string | null
  source_url: string | null
  crop_image_path: string | null
  confidence: number
  created_at: string
  updated_at: string
}

export interface QuestionUpdate {
  content?: string
  question_type?: QuestionType
  answer_markdown?: string
  company?: string | null
  direction?: string | null
  interview_round?: string | null
}

export interface SearchItem extends Question {
  rank: number
  headline: string
}

export interface Paged<T> {
  items: T[]
  total: number
}
