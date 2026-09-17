import { fireEvent, screen, waitFor } from '@testing-library/react'
import TasksPage from './TasksPage'
import { renderWithProviders } from '../test/test-utils'
import type { Paged, TaskItem } from '../types'

const listTasks = vi.fn()
const retryTask = vi.fn()

vi.mock('../api/client', () => ({
  listTasks: (...args: unknown[]) => listTasks(...args),
  retryTask: (...args: unknown[]) => retryTask(...args),
}))

function task(over: Partial<TaskItem>): TaskItem {
  return {
    id: 1, post_id: 1, task_type: 'manual_images', status: 'pending', retry_count: 0,
    error_message: null, stage_stats: null, created_at: '2026-09-16T08:00:00Z', finished_at: null,
    ...over,
  }
}

it('渲染任务行与状态标签', async () => {
  listTasks.mockResolvedValue({
    items: [task({ id: 7, status: 'failed', error_message: 'boom' })],
    total: 1,
  } as Paged<TaskItem>)
  renderWithProviders(<TasksPage />, { route: '/tasks' })
  expect(await screen.findByText('7')).toBeInTheDocument()
  expect(screen.getByText('失败')).toBeInTheDocument()
  expect(screen.getByText('boom')).toBeInTheDocument()
})

it('failed 行点击重试调用 retryTask(7)', async () => {
  listTasks.mockResolvedValue({ items: [task({ id: 7, status: 'failed' })], total: 1 })
  retryTask.mockResolvedValue(task({ id: 7, status: 'pending' }))
  renderWithProviders(<TasksPage />, { route: '/tasks' })
  await screen.findByText('7')
  fireEvent.click(screen.getByRole('button', { name: '重试' }))
  await waitFor(() => expect(retryTask).toHaveBeenCalledWith(7))
})

it('done 任务不显示重试按钮', async () => {
  listTasks.mockResolvedValue({ items: [task({ status: 'done' })], total: 1 })
  renderWithProviders(<TasksPage />, { route: '/tasks' })
  await screen.findByText('完成')
  expect(screen.queryByRole('button', { name: '重试' })).not.toBeInTheDocument()
})
