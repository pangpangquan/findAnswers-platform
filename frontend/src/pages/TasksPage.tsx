import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Card, Select, Space, Table, Tag } from 'antd'
import { useState } from 'react'
import { listTasks, retryTask } from '../api/client'
import { TASK_STATUS_META, TASK_TYPE_LABELS } from '../constants'
import type { TaskItem, TaskStatus } from '../types'
import { formatDate } from '../utils/format'

const ACTIVE: TaskStatus[] = ['pending', 'processing']

export default function TasksPage() {
  const [status, setStatus] = useState<TaskStatus | undefined>()
  const [page, setPage] = useState(1)
  const queryClient = useQueryClient()

  const { data, isLoading } = useQuery({
    queryKey: ['tasks', status, page],
    queryFn: () => listTasks({ status, page, pageSize: 20 }),
    refetchInterval: (query) =>
      query.state.data?.items.some((t) => ACTIVE.includes(t.status)) ? 2000 : false,
  })

  const retry = useMutation({
    mutationFn: (id: number) => retryTask(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['tasks'] }),
  })

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 140,
      render: (s: TaskStatus) => <Tag color={TASK_STATUS_META[s].color}>{TASK_STATUS_META[s].label}</Tag>,
    },
    {
      title: '类型',
      dataIndex: 'task_type',
      width: 100,
      render: (t: TaskItem['task_type']) => TASK_TYPE_LABELS[t],
    },
    {
      title: '错误信息',
      dataIndex: 'error_message',
      ellipsis: true,
      render: (v: string | null) => v ?? '-',
    },
    { title: '重试次数', dataIndex: 'retry_count', width: 90 },
    { title: '创建时间', dataIndex: 'created_at', width: 170, render: formatDate },
    {
      title: '操作',
      width: 90,
      render: (_: unknown, r: TaskItem) =>
        r.status === 'failed' ? (
          <Button size="small" onClick={() => retry.mutate(r.id)}>
            重试
          </Button>
        ) : null,
    },
  ]

  return (
    <Card title="任务中心">
      <Space style={{ marginBottom: 16 }}>
        <Select
          allowClear
          placeholder="按状态筛选"
          style={{ width: 180 }}
          value={status}
          onChange={(v) => {
            setStatus(v)
            setPage(1)
          }}
          options={Object.entries(TASK_STATUS_META).map(([value, m]) => ({ value, label: m.label }))}
        />
      </Space>
      <Table<TaskItem>
        rowKey="id"
        loading={isLoading}
        columns={columns}
        dataSource={data?.items}
        pagination={{ current: page, pageSize: 20, total: data?.total ?? 0, onChange: setPage }}
      />
    </Card>
  )
}
