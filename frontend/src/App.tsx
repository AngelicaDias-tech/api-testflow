import { Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ProjectsPage from './pages/ProjectsPage'
import RequestsPage from './pages/RequestsPage'
import NewRequestPage from './pages/NewRequestPage'
import WorkbenchPage from './pages/WorkbenchPage'
import ExecutionPage from './pages/ExecutionPage'
import HistoryPage from './pages/HistoryPage'

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<ProjectsPage />} />
        <Route path="/projects/:projectId" element={<RequestsPage />} />
        <Route path="/projects/:projectId/new" element={<NewRequestPage />} />
        <Route path="/projects/:projectId/requests/:requestId" element={<WorkbenchPage />} />
        <Route path="/projects/:projectId/requests/:requestId/history" element={<HistoryPage />} />
        <Route
          path="/projects/:projectId/requests/:requestId/executions/:executionId"
          element={<ExecutionPage />}
        />
      </Routes>
    </Layout>
  )
}
