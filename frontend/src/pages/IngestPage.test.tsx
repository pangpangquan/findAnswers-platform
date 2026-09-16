import { fireEvent, screen, waitFor } from '@testing-library/react'
import IngestPage from './IngestPage'
import { renderWithProviders } from '../test/test-utils'

const uploadImages = vi.fn()

vi.mock('../api/client', () => ({
  uploadImages: (...args: unknown[]) => uploadImages(...args),
}))

vi.mock('react-router-dom', async () => ({
  ...(await vi.importActual<typeof import('react-router-dom')>('react-router-dom')),
  useNavigate: () => vi.fn(),
}))

function png(name: string) {
  return new File(['x'], name, { type: 'image/png' })
}

it('渲染拖拽区与按钮', () => {
  renderWithProviders(<IngestPage />)
  expect(screen.getByText('点击或拖拽图片到此处')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: '开始处理' })).toBeInTheDocument()
})

it('空列表提交给出警告且不调 API', async () => {
  renderWithProviders(<IngestPage />)
  fireEvent.click(screen.getByRole('button', { name: '开始处理' }))
  await waitFor(() => expect(screen.getByText('请先添加图片')).toBeInTheDocument())
  expect(uploadImages).not.toHaveBeenCalled()
})

it('collectPasteFiles 只保留图片', async () => {
  const { collectPasteFiles } = await import('./IngestPage')
  const files = [png('a.png'), new File(['t'], 't.txt', { type: 'text/plain' })]
  expect(collectPasteFiles(files)).toHaveLength(1)
})
