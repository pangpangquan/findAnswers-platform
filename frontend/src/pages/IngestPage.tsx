import { InboxOutlined } from '@ant-design/icons'
import { useMutation } from '@tanstack/react-query'
import { App as AntApp, Button, Card, Typography, Upload } from 'antd'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadImages } from '../api/client'

export function collectPasteFiles(files: File[]): File[] {
  return files.filter((f) => f.type.startsWith('image/'))
}

export default function IngestPage() {
  const [files, setFiles] = useState<File[]>([])
  const navigate = useNavigate()
  const { message } = AntApp.useApp()

  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const imgs = collectPasteFiles(Array.from(e.clipboardData?.files ?? []))
      if (imgs.length) setFiles((prev) => [...prev, ...imgs])
    }
    window.addEventListener('paste', onPaste)
    return () => window.removeEventListener('paste', onPaste)
  }, [])

  const mutation = useMutation({
    mutationFn: uploadImages,
    onSuccess: (_data, vars) => {
      message.success(`已提交 ${vars.length} 张图片，正在处理`)
      setFiles([])
      navigate('/tasks')
    },
    onError: () => message.error('上传失败，请重试'),
  })

  return (
    <Card title="上传面经截图">
      <Typography.Paragraph type="secondary">
        支持拖拽 / 点击选择 / Ctrl+V 粘贴截图，可一次多张，提交后自动排队处理
      </Typography.Paragraph>
      <Upload.Dragger
        multiple
        accept="image/png,image/jpeg,image/webp"
        showUploadList={false}
        beforeUpload={(_, fileList) => {
          setFiles(fileList.filter((f) => f.type.startsWith('image/')))
          return false
        }}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽图片到此处</p>
        <p className="ant-upload-hint">png / jpeg / webp，单张 ≤ 20MB</p>
      </Upload.Dragger>
      <Typography.Paragraph style={{ marginTop: 16 }}>已选择 {files.length} 张图片</Typography.Paragraph>
      <Button
        type="primary"
        size="large"
        loading={mutation.isPending}
        onClick={() => {
          if (!files.length) {
            message.warning('请先添加图片')
            return
          }
          mutation.mutate(files)
        }}
      >
        开始处理
      </Button>
    </Card>
  )
}
