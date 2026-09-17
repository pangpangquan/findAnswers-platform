import { fireEvent, screen, waitFor } from '@testing-library/react'
import QuestionDetailPage from './QuestionDetailPage'
import { renderWithProviders } from '../test/test-utils'
import type { Question } from '../types'

const getQuestion = vi.fn()
const updateQuestion = vi.fn()
const deleteQuestion = vi.fn()

vi.mock('../api/client', () => ({
  getQuestion: (...args: unknown[]) => getQuestion(...args),
  updateQuestion: (...args: unknown[]) => updateQuestion(...args),
  deleteQuestion: (...args: unknown[]) => deleteQuestion(...args),
}))

vi.mock('react-router-dom', async () => ({
  ...(await vi.importActual<typeof import('react-router-dom')>('react-router-dom')),
  useNavigate: () => navigateMock,
  useParams: () => ({ id: '1' }),
}))
const navigateMock = vi.fn()

const fixture: Question = {
  id: 1, post_id: 1, image_id: null, content: '讲讲 TCP 三次握手', question_type: 'eight_legged',
  answer_markdown: '- 第一次握手\n---\n详解', answer_source: 'ai', company: '字节跳动',
  direction: '后端', interview_round: '一面', source_url: 'https://x.com/p/1',
  crop_image_path: null, confidence: 0.9, created_at: '2026-09-16T08:00:00Z',
  updated_at: '2026-09-16T08:00:00Z',
}

it('渲染题干、元信息与答案', async () => {
  getQuestion.mockResolvedValue(fixture)
  renderWithProviders(<QuestionDetailPage />, { route: '/questions/1' })
  expect(await screen.findByText('讲讲 TCP 三次握手')).toBeInTheDocument()
  expect(screen.getByText('AI 生成')).toBeInTheDocument()
  expect(screen.getByText('第一次握手')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: '查看原帖' })).toHaveAttribute('href', 'https://x.com/p/1')
})

it('编辑并保存调用 updateQuestion', async () => {
  getQuestion.mockResolvedValue(fixture)
  updateQuestion.mockResolvedValue(fixture)
  renderWithProviders(<QuestionDetailPage />, { route: '/questions/1' })
  await screen.findByText('讲讲 TCP 三次握手')
  fireEvent.click(screen.getByRole('button', { name: '编辑' }))
  const textarea = await screen.findByLabelText('答案')
  fireEvent.change(textarea, { target: { value: '修正后的答案' } })
  fireEvent.click(screen.getByRole('button', { name: '保存' }))
  await waitFor(() =>
    expect(updateQuestion).toHaveBeenCalledWith(
      1,
      expect.objectContaining({ answer_markdown: '修正后的答案' }),
    ),
  )
})

it('删除后跳回列表', async () => {
  getQuestion.mockResolvedValue(fixture)
  deleteQuestion.mockResolvedValue(undefined)
  renderWithProviders(<QuestionDetailPage />, { route: '/questions/1' })
  await screen.findByText('讲讲 TCP 三次握手')
  fireEvent.click(screen.getByRole('button', { name: '删除' }))
  fireEvent.click(await screen.findByRole('button', { name: '确定' }))
  await waitFor(() => expect(deleteQuestion).toHaveBeenCalledWith(1))
  await waitFor(() => expect(navigateMock).toHaveBeenCalledWith('/questions'))
})
