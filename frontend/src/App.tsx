import { App as AntApp, ConfigProvider, Layout, Menu } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import {
  DownloadOutlined,
  FileSearchOutlined,
  OrderedListOutlined,
  UnorderedListOutlined,
  UploadOutlined,
} from '@ant-design/icons'
import { Link, Route, Routes, useLocation } from 'react-router-dom'
import IngestPage from './pages/IngestPage'
import TasksPage from './pages/TasksPage'
import QuestionsPage from './pages/QuestionsPage'
import QuestionDetailPage from './pages/QuestionDetailPage'
import SearchPage from './pages/SearchPage'
import ExportPage from './pages/ExportPage'

const { Sider, Content, Header } = Layout

const MENU = [
  { key: '/ingest', icon: <UploadOutlined />, label: <Link to="/ingest">上传</Link> },
  { key: '/tasks', icon: <OrderedListOutlined />, label: <Link to="/tasks">任务中心</Link> },
  { key: '/questions', icon: <UnorderedListOutlined />, label: <Link to="/questions">题库</Link> },
  { key: '/search', icon: <FileSearchOutlined />, label: <Link to="/search">搜索</Link> },
  { key: '/export', icon: <DownloadOutlined />, label: <Link to="/export">导出</Link> },
]

export default function App() {
  const { pathname } = useLocation()
  const selected = '/' + (pathname.split('/')[1] || 'ingest')
  return (
    <ConfigProvider locale={zhCN} button={{ autoInsertSpace: false }}>
      <AntApp>
      <Layout style={{ minHeight: '100vh' }}>
        <Sider>
          <Header style={{ color: '#fff', fontSize: 16, whiteSpace: 'nowrap' }}>面经整理平台</Header>
          <Menu theme="dark" mode="inline" selectedKeys={[selected]} items={MENU} />
        </Sider>
        <Layout>
          <Content style={{ padding: 24 }}>
            <Routes>
              <Route path="/" element={<IngestPage />} />
              <Route path="/ingest" element={<IngestPage />} />
              <Route path="/tasks" element={<TasksPage />} />
              <Route path="/questions" element={<QuestionsPage />} />
              <Route path="/questions/:id" element={<QuestionDetailPage />} />
              <Route path="/search" element={<SearchPage />} />
              <Route path="/export" element={<ExportPage />} />
            </Routes>
          </Content>
        </Layout>
      </Layout>
      </AntApp>
    </ConfigProvider>
  )
}
