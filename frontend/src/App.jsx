import { Routes, Route, Navigate, NavLink } from 'react-router-dom'
import Projects from './pages/Projects.jsx'
import ProjectDetail from './pages/ProjectDetail.jsx'
import ResearchDashboard from './pages/ResearchDashboard.jsx'
import RunDetail from './pages/RunDetail.jsx'
import SettingsPage from './pages/Settings.jsx'
import Researches from './pages/Researches.jsx'
import { t } from './i18n.js'

const nav = [
  { to: '/projects', label: t.nav.projects },
  { to: '/researches', label: t.nav.researches },
  { to: '/settings', label: t.nav.settings },
]

function Layout({ children }) {
  return (
    <div className="min-h-screen">
      <header className="bg-ink text-white sticky top-0 z-20">
        <div className="w-full px-4 sm:px-6 lg:px-10 h-14 flex items-center gap-8">
          <NavLink to="/" className="font-bold tracking-tight text-lg">
            GEO<span className="text-emerald-400"> Lab</span>
          </NavLink>
          <nav className="flex gap-1">
            {nav.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  `px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${
                    isActive ? 'bg-white/10 text-white' : 'text-slate-300 hover:text-white hover:bg-white/5'
                  }`
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="w-full px-4 sm:px-6 lg:px-10 py-6">{children}</main>
    </div>
  )
}

export default function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<Navigate to="/projects" replace />} />
        <Route path="/projects" element={<Projects />} />
        <Route path="/projects/:projectId" element={<ProjectDetail />} />
        <Route path="/projects/:projectId/research/:researchId" element={<ResearchDashboard />} />
        <Route path="/research/:researchId" element={<ResearchDashboard />} />
        <Route path="/runs/:runId" element={<RunDetail />} />
        <Route path="/researches" element={<Researches />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Routes>
    </Layout>
  )
}
