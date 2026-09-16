import { screen } from '@testing-library/react'
import App from './App'
import { renderWithProviders } from './test/test-utils'

describe('App', () => {
  it('渲染布局与菜单', () => {
    renderWithProviders(<App />, { route: '/ingest' })
    expect(screen.getByText('面经整理平台')).toBeInTheDocument()
    expect(screen.getByText('上传面经截图')).toBeInTheDocument()
    expect(screen.getByText('任务中心')).toBeInTheDocument()
  })
})
