import { uploadImages } from './client'

const fetchMock = vi.fn()

beforeEach(() => {
  vi.stubGlobal('fetch', fetchMock)
  fetchMock.mockClear()
  fetchMock.mockResolvedValue(
    new Response(JSON.stringify({ post_id: 1, task_id: 2 }), { status: 201 }),
  )
})

it('uploadImages 用 FormData POST /api/ingest/images，字段名 files', async () => {
  const files = [new File(['a'], 'a.png', { type: 'image/png' })]
  const res = await uploadImages(files)
  expect(res).toEqual({ post_id: 1, task_id: 2 })
  const [url, init] = fetchMock.mock.calls[0]
  expect(url).toBe('/api/ingest/images')
  expect(init.method).toBe('POST')
  expect(init.body).toBeInstanceOf(FormData)
  expect(init.body.getAll('files')).toHaveLength(1)
})

it('listTasks 传 status/page/page_size 查询参数', async () => {
  fetchMock.mockResolvedValueOnce(
    new Response(JSON.stringify({ items: [], total: 0 }), { status: 200 }),
  )
  const { listTasks } = await import('./client')
  await listTasks({ status: 'failed', page: 2, pageSize: 20 })
  expect(fetchMock.mock.calls[0][0]).toBe('/api/tasks?status=failed&page=2&page_size=20')
})
