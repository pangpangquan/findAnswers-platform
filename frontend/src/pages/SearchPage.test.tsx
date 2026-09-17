import { fireEvent, screen, waitFor } from '@testing-library/react'
import SearchPage from './SearchPage'
import { renderWithProviders } from '../test/test-utils'
import type { SearchItem } from '../types'

const searchQuestions = vi.fn()

vi.mock('../api/client', () => ({
  searchQuestions: (...args: unknown[]) => searchQuestions(...args),
}))

vi.mock('react-router-dom', async () => ({
  ...(await vi.importActual<typeof import('react-router-dom')>('react-router-dom')),
  useNavigate: () => navigateMock,
}))
const navigateMock = vi.fn()

const item: SearchItem = {
  id: 1, post_id: 1, image_id: null, content: '讲讲 MySQL 的 MVCC', question_type: 'eight_legged',
  answer_markdown: null, answer_source: 'ai', company: '字节跳动', direction: null,
  interview_round: null, source_url: null, crop_image_path: null, confidence: 0.9,
  created_at: '2026-09-16T08:00:00Z', updated_at: '2026-09-16T08:00:00Z',
  rank: 1.2, headline: '讲讲 MySQL 的 <em>MVCC</em> 实现原理',
}

function submit() {
  fireEvent.submit(screen.getByPlaceholderText('搜索题干 / 答案 / 公司').closest('form')!)
}

it('回车搜索并渲染高亮结果', async () => {
  searchQuestions.mockResolvedValue([item])
  renderWithProviders(<SearchPage />, { route: '/search' })
  fireEvent.change(screen.getByPlaceholderText('搜索题干 / 答案 / 公司'), { target: { value: 'MVCC' } })
  submit()
  expect(await screen.findByText('MVCC', { selector: 'em' })).toBeInTheDocument()
  expect(screen.getByText('相关度 1.200')).toBeInTheDocument()
})

it('点击结果跳详情', async () => {
  searchQuestions.mockResolvedValue([item])
  renderWithProviders(<SearchPage />, { route: '/search' })
  fireEvent.change(screen.getByPlaceholderText('搜索题干 / 答案 / 公司'), { target: { value: 'MVCC' } })
  submit()
  const em = await screen.findByText('MVCC', { selector: 'em' })
  fireEvent.click(em.closest('[data-result-id]')!)
  await waitFor(() => expect(navigateMock).toHaveBeenCalledWith('/questions/1'))
})

it('空关键词不触发请求', () => {
  searchQuestions.mockClear()
  renderWithProviders(<SearchPage />, { route: '/search' })
  submit()
  expect(searchQuestions).not.toHaveBeenCalled()
})
