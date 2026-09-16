const BASE = '/api'

function qs(params: Record<string, unknown>): string {
  const sp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') sp.set(k, String(v))
  }
  const s = sp.toString()
  return s ? `?${s}` : ''
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, init)
  if (!resp.ok) throw new Error(`API ${resp.status}: ${await resp.text().catch(() => '')}`)
  if (resp.status === 204) return undefined as T
  return resp.json() as Promise<T>
}

function jsonInit(method: string, body: unknown): RequestInit {
  return { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }
}

export async function uploadImages(files: File[]) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  return request<{ post_id: number; task_id: number }>('/ingest/images', { method: 'POST', body: fd })
}

export async function listTasks(p: { status?: string; page?: number; pageSize?: number } = {}) {
  return request<Paged<TaskItem>>(`/tasks${qs({ status: p.status, page: p.page, page_size: p.pageSize })}`)
}

export async function retryTask(id: number) {
  return request<TaskItem>(`/tasks/${id}/retry`, { method: 'POST' })
}

export async function listQuestions(
  p: {
    question_type?: string
    answer_source?: string
    company?: string
    direction?: string
    q?: string
    page?: number
    pageSize?: number
  } = {},
) {
  return request<Paged<Question>>(
    `/questions${qs({
      question_type: p.question_type,
      answer_source: p.answer_source,
      company: p.company,
      direction: p.direction,
      q: p.q,
      page: p.page,
      page_size: p.pageSize,
    })}`,
  )
}

export async function getQuestion(id: string | number) {
  return request<Question>(`/questions/${id}`)
}

export async function updateQuestion(id: string | number, body: QuestionUpdate) {
  return request<Question>(`/questions/${id}`, jsonInit('PATCH', body))
}

export async function deleteQuestion(id: string | number) {
  return request<void>(`/questions/${id}`, { method: 'DELETE' })
}

export async function searchQuestions(q: string) {
  const data = await request<{ items: SearchItem[] }>(`/search${qs({ q })}`)
  return data.items
}
