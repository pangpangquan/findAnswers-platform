import { DownloadOutlined } from '@ant-design/icons'
import { Button, Card, Typography } from 'antd'

export default function ExportPage() {
  return (
    <Card title="导出题库">
      <Typography.Paragraph>
        将当前全部题目导出为一个 Markdown 文件（含公司/方向/轮次/来源链接/答案）。
      </Typography.Paragraph>
      <Button type="primary" icon={<DownloadOutlined />} onClick={() => window.open('/api/export?format=md')}>
        导出全部（Markdown）
      </Button>
      <Typography.Paragraph type="secondary" style={{ marginTop: 16 }}>
        按筛选条件导出为未来增强（需后端支持过滤参数）。
      </Typography.Paragraph>
    </Card>
  )
}
