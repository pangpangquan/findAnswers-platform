import { useQuery } from '@tanstack/react-query'
import { Card, Input, Select, Space, Table, Tag } from 'antd'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { listQuestions } from '../api/client'
import { ANSWER_SOURCE_META, LOW_CONFIDENCE_THRESHOLD, QUESTION_TYPE_LABELS } from '../constants'
import type { AnswerSource, Question, QuestionType } from '../types'

export default function QuestionsPage() {
  const [questionType, setQuestionType] = useState<QuestionType | undefined>()
  const [answerSource, setAnswerSource] = useState<AnswerSource | undefined>()
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const [submitted, setSubmitted] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['questions', questionType, answerSource, submitted, page],
    queryFn: () =>
      listQuestions({
        question_type: questionType,
        answer_source: answerSource,
        q: submitted || undefined,
        page,
        pageSize: 20,
      }),
  })

  const columns = [
    {
      title: '题干',
      dataIndex: 'content',
      ellipsis: true,
      render: (v: string, r: Question) => <Link to={`/questions/${r.id}`}>{v}</Link>,
    },
    {
      title: '题型',
      width: 110,
      render: (_: unknown, r: Question) => <Tag>{QUESTION_TYPE_LABELS[r.question_type]}</Tag>,
    },
    { title: '公司', dataIndex: 'company', width: 120, render: (v: string | null) => v ?? '-' },
    { title: '方向', dataIndex: 'direction', width: 100, render: (v: string | null) => v ?? '-' },
    {
      title: '轮次',
      dataIndex: 'interview_round',
      width: 90,
      render: (v: string | null) => v ?? '-',
    },
    {
      title: '答案来源',
      dataIndex: 'answer_source',
      width: 110,
      render: (s: AnswerSource) => <Tag color={ANSWER_SOURCE_META[s].color}>{ANSWER_SOURCE_META[s].label}</Tag>,
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      width: 130,
      render: (v: number) => (
        <Tag color={v < LOW_CONFIDENCE_THRESHOLD ? 'warning' : 'default'}>
          {v < LOW_CONFIDENCE_THRESHOLD ? '低置信度 ' : ''}
          {v.toFixed(2)}
        </Tag>
      ),
    },
  ]

  return (
    <Card title="题库">
      <Space wrap style={{ marginBottom: 16 }}>
        <Select
          allowClear
          placeholder="题型"
          style={{ width: 140 }}
          value={questionType}
          onChange={(v) => {
            setQuestionType(v)
            setPage(1)
          }}
          options={Object.entries(QUESTION_TYPE_LABELS).map(([value, label]) => ({ value, label }))}
        />
        <Select
          allowClear
          placeholder="答案来源"
          style={{ width: 140 }}
          value={answerSource}
          onChange={(v) => {
            setAnswerSource(v)
            setPage(1)
          }}
          options={Object.entries(ANSWER_SOURCE_META).map(([value, m]) => ({ value, label: m.label }))}
        />
        <form
          onSubmit={(e) => {
            e.preventDefault()
            setSubmitted(q.trim())
            setPage(1)
          }}
        >
          <Input.Search
            allowClear
            placeholder="搜索关键词"
            style={{ width: 260 }}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </form>
      </Space>
      <Table<Question>
        rowKey="id"
        loading={isLoading}
        columns={columns}
        dataSource={data?.items}
        pagination={{ current: page, pageSize: 20, total: data?.total ?? 0, onChange: setPage }}
      />
    </Card>
  )
}
