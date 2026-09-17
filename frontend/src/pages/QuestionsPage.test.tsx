import { fireEvent, screen, waitFor } from '@testing-library/react'
import QuestionsPage from './QuestionsPage'
import { renderWithProviders } from '../test/test-utils'
import type { Paged, Question } from '../types'

const listQuestions = vi.fn()

vi.mock('../api/client', () => ({
  listQuestions: (...args: unknown[]) => listQuestions(...args),
}))

vi.mock('react-router-dom', async () => ({
  ...(await vi.importActual<typeof import('react-router-dom')>('react-router-dom')),
  useNavigate: () => navigateMock,
}))
const navigateMock = vi.fn()

function q(over: Partial<Question>): Question {
  return {
    id: 1, post_id: 1, image_id: null, content: '讲讲 TCP 三次握手', question_type: 'eight_legged',
    answer_markdown: '三步握手', answer_source: 'ai', company: '字节跳动', direction: '后端',
    interview_round: '一面', source_url: null, crop_image_path: null, confidence: 0.9,
    created_at: '2026-09-16T08:00:00Z', updated_at: '2026-09-16T08:00:00Z', ...over,
  }
}

it('渲染题目行、题型与答案来源徽标', async () => {
  listQuestions.mockResolvedValue({ items: [q({})], total: 1 })
  renderWithProviders(<QuestionsPage />, { route: '/questions' })
  expect(await screen.findByText('讲讲 TCP 三次握手')).toBeInTheDocument()
  expect(screen.getByText('八股')).toBeInTheDocument()
  expect(screen.getByText('AI 生成')).toBeInTheDocument()
})

it('低置信度题目显示警告标记', async () => {
  listQuestions.mockResolvedValue({ items: [q({ id: 2, confidence: 0.4 })], total: 1 })
  renderWithProviders(<QuestionsPage />, { route: '/questions' })
  await screen.findByText(/低置信度/)
})

it('输入关键词回车触发带 q 参数的查询', async () => {
  listQuestions.mockResolvedValue({ items: [], total: 0 })
  renderWithProviders(<QuestionsPage />, { route: '/questions' })
  await screen.findByPlaceholderText('搜索关键词')
  fireEvent.change(screen.getByPlaceholderText('搜索关键词'), { target: { value: 'MVCC' } })
  fireEvent.submit(screen.getByPlaceholderText('搜索关键词').closest('form')!)
  await waitFor(() =>
    expect(listQuestions).toHaveBeenLastCalledWith(expect.objectContaining({ q: 'MVCC', page: 1 })),
  )
})
