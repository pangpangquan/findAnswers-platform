import { fireEvent, screen } from '@testing-library/react'
import ExportPage from './ExportPage'
import { renderWithProviders } from '../test/test-utils'

it('点击导出按钮以正确 URL 打开下载', () => {
  const open = vi.fn()
  vi.stubGlobal('open', open)
  renderWithProviders(<ExportPage />, { route: '/export' })
  fireEvent.click(screen.getByRole('button', { name: /导出全部/ }))
  expect(open).toHaveBeenCalledWith('/api/export?format=md')
})
