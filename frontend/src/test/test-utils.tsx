import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { App as AntApp, ConfigProvider } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { MemoryRouter } from 'react-router-dom'

export function renderWithProviders(ui: ReactElement, { route = '/' } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return {
    ...render(
      <QueryClientProvider client={queryClient}>
        <ConfigProvider locale={zhCN} button={{ autoInsertSpace: false }}>
          <AntApp>
            <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
          </AntApp>
        </ConfigProvider>
      </QueryClientProvider>,
    ),
    queryClient,
  }
}
