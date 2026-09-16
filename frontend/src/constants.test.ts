import { ANSWER_SOURCE_META, QUESTION_TYPE_LABELS, TASK_STATUS_META } from './constants'

it('题型标签与后端一致', () => {
  expect(QUESTION_TYPE_LABELS.eight_legged).toBe('八股')
  expect(QUESTION_TYPE_LABELS.handwritten_code).toBe('手撕代码')
})

it('任务状态五种齐全且有颜色', () => {
  expect(Object.keys(TASK_STATUS_META)).toHaveLength(5)
  expect(TASK_STATUS_META.failed.color).toBe('error')
})

it('答案来源两种', () => {
  expect(ANSWER_SOURCE_META.original.label).toBe('来自原帖')
  expect(ANSWER_SOURCE_META.ai.label).toBe('AI 生成')
})
