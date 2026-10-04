import { Routes, Route, Navigate } from 'react-router-dom'
import AuthGate from './AuthGate.jsx'
import Account from './pages/Account.jsx'
import OrganizationPage from './pages/Organization.jsx'
import Projects from './pages/Projects.jsx'
import ProjectDetail from './pages/ProjectDetail.jsx'
import ResearchDashboard from './pages/ResearchDashboard.jsx'
import RunDetail from './pages/RunDetail.jsx'
import SettingsPage from './pages/Settings.jsx'
import Researches from './pages/Researches.jsx'
import Login from './pages/Login.jsx'
import Register from './pages/Register.jsx'

export default function App() {
  return (
    <AuthGate>
      <Routes>
        <Route path="/" element={<Navigate to="/projects" replace />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/account" element={<Account />} />
        <Route path="/organization" element={<OrganizationPage />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/projects/:projectId" element={<ProjectDetail />} />
        <Route path="/projects/:projectId/research/:researchId" element={<ResearchDashboard />} />
        <Route path="/research/:researchId" element={<ResearchDashboard />} />
        <Route path="/runs/:runId" element={<RunDetail />} />
        <Route path="/researches" element={<Researches />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Routes>
    </AuthGate>
  )
}