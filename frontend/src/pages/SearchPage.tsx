import { useQuery } from '@tanstack/react-query'
import { Card, Empty, Input, List, Space, Tag, Typography } from 'antd'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { searchQuestions } from '../api/client'
import { ANSWER_SOURCE_META, QUESTION_TYPE_LABELS } from '../constants'

export default function SearchPage() {
  const [input, setInput] = useState('')
  const [submitted, setSubmitted] = useState('')
  const navigate = useNavigate()

  const { data, isFetching } = useQuery({
    queryKey: ['search', submitted],
    queryFn: () => searchQuestions(submitted),
    enabled: submitted.trim().length > 0,
  })

  return (
    <Card title="全文搜索">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          setSubmitted(input.trim())
        }}
      >
        <Input.Search
          enterButton
          size="large"
          placeholder="搜索题干 / 答案 / 公司"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          loading={isFetching}
        />
      </form>
      <div style={{ marginTop: 16 }}>
        {!submitted.trim() ? (
          <Empty description="输入关键词开始搜索（支持中文分词）" />
        ) : (
          <List
            dataSource={data ?? []}
            locale={{ emptyText: '没有匹配的题目' }}
            renderItem={(item) => (
              <List.Item
                style={{ cursor: 'pointer' }}
                data-result-id={item.id}
                onClick={() => navigate(`/questions/${item.id}`)}
              >
                <List.Item.Meta
                  title={<span dangerouslySetInnerHTML={{ __html: item.headline }} />}
                  description={
                    <Space wrap>
                      <Tag>{QUESTION_TYPE_LABELS[item.question_type]}</Tag>
                      {item.company && <Tag>{item.company}</Tag>}
                      <Tag color={ANSWER_SOURCE_META[item.answer_source].color}>
                        {ANSWER_SOURCE_META[item.answer_source].label}
                      </Tag>
                      <Typography.Text type="secondary">相关度 {item.rank.toFixed(3)}</Typography.Text>
                    </Space>
                  }
                />
              </List.Item>
            )}
          />
        )}
      </div>
    </Card>
  )
}
