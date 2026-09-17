import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Button, Card, Descriptions, Form, Input, Popconfirm, Select, Space, Tag, Typography } from 'antd'
import ReactMarkdown from 'react-markdown'
import rehypeHighlight from 'rehype-highlight'
import remarkGfm from 'remark-gfm'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { deleteQuestion, getQuestion, updateQuestion } from '../api/client'
import { ANSWER_SOURCE_META, QUESTION_TYPE_LABELS, QUESTION_TYPE_OPTIONS } from '../constants'
import type { QuestionUpdate } from '../types'

export default function QuestionDetailPage() {
  const { id } = useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [form] = Form.useForm()
  const [editing, setEditing] = useState(false)

  const { data: q } = useQuery({ queryKey: ['question', id], queryFn: () => getQuestion(id!) })

  const save = useMutation({
    mutationFn: (values: QuestionUpdate) => updateQuestion(Number(id!), values),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['question', id] })
      queryClient.invalidateQueries({ queryKey: ['questions'] })
      setEditing(false)
    },
  })
  const remove = useMutation({
    mutationFn: () => deleteQuestion(Number(id!) ),
    onSuccess: () => navigate('/questions'),
  })

  if (!q) return null
  const startEdit = () => {
    form.setFieldsValue({
      content: q.content,
      question_type: q.question_type,
      answer_markdown: q.answer_markdown ?? '',
      company: q.company,
      direction: q.direction,
      interview_round: q.interview_round,
    })
    setEditing(true)
  }

  return (
    <Card
      title={q.content}
      extra={
        editing ? (
          <Space>
            <Button onClick={() => setEditing(false)}>取消</Button>
          </Space>
        ) : (
          <Space>
            <Button
              type="primary"
              onClick={() => {
                startEdit()
              }}
            >
              编辑
            </Button>
            <Popconfirm title="确认删除该题目？" onConfirm={() => remove.mutate()}>
              <Button danger>删除</Button>
            </Popconfirm>
          </Space>
        )
      }
    >
      {editing ? (
        <Form
          form={form}
          layout="vertical"
          onFinish={(values) => {
            save.mutate(values)
          }}
        >
          <Form.Item label="题干" name="content" rules={[{ required: true, min: 4 }]}>
            <Input.TextArea rows={2} />
          </Form.Item>
          <Form.Item label="题型" name="question_type" rules={[{ required: true }]}>
            <Select options={QUESTION_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item label="答案" name="answer_markdown">
            <Input.TextArea rows={14} />
          </Form.Item>
          <Space wrap>
            <Form.Item label="公司" name="company">
              <Input />
            </Form.Item>
            <Form.Item label="方向" name="direction">
              <Input />
            </Form.Item>
            <Form.Item label="轮次" name="interview_round">
              <Input />
            </Form.Item>
          </Space>
          <div>
            <Button type="primary" htmlType="submit">
              保存
            </Button>
          </div>
        </Form>
      ) : (
        <>
          <Descriptions size="small" column={4} style={{ marginBottom: 16 }}>
            <Descriptions.Item label="题型">
              <Tag>{QUESTION_TYPE_LABELS[q.question_type]}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="答案来源">
              <Tag color={ANSWER_SOURCE_META[q.answer_source].color}>
                {ANSWER_SOURCE_META[q.answer_source].label}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="公司/方向/轮次">
              {[q.company, q.direction, q.interview_round].filter(Boolean).join(' / ') || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="置信度">{q.confidence.toFixed(2)}</Descriptions.Item>
          </Descriptions>
          {q.source_url && (
            <Typography.Paragraph>
              <a href={q.source_url} target="_blank" rel="noreferrer">
                查看原帖
              </a>
            </Typography.Paragraph>
          )}
          <div className="answer-markdown">
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
              {q.answer_markdown ?? '（待补充）'}
            </ReactMarkdown>
          </div>
        </>
      )}
    </Card>
  )
}
