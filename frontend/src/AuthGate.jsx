import { useEffect, useState } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { api, onAuthFail } from './api.js'

export default function AuthGate({ children }) {
  const location = useLocation()
  const [state, setState] = useState('loading')
  const [user, setUser] = useState(null)

  function checkAuth() {
    setState('loading')
    api
      .me()
      .then((u) => {
        setUser(u)
        setState('auth')
      })
      .catch(() => {
        setState('anon')
      })
  }

  useEffect(() => {
    onAuthFail(() => {
      setUser(null)
      setState('anon')
    })
  }, [])

  useEffect(() => {
    checkAuth()
  }, [location.pathname])

  function doLogout() {
    api
      .logout()
      .then(() => {
        setUser(null)
        setState('anon')
      })
      .catch(() => {
        setUser(null)
        setState('anon')
      })
  }

  if (state === 'loading') {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-slate-400 text-sm flex items-center gap-2">
          <span className="inline-block w-4 h-4 border-2 border-slate-300 border-t-emerald-500 rounded-full animate-spin" />
          Загрузка…
        </div>
      </div>
    )
  }

  if (state === 'anon') {
    if (location.pathname === '/login' || location.pathname === '/register') {
      return children
    }
    return <Navigate to="/login" replace />
  }

  // state === 'auth'
  if (location.pathname === '/login' || location.pathname === '/register') {
    return <Navigate to="/projects" replace />
  }

  return (
    <AppLayout user={user} onLogout={doLogout}>
      {children}
    </AppLayout>
  )
}

function AppLayout({ user, onLogout, children }) {
  return (
    <div className="min-h-screen">
      <header className="bg-ink text-white sticky top-0 z-20">
        <div className="w-full px-4 sm:px-6 lg:px-10 h-14 flex items-center gap-8">
          <a href="/projects" className="font-bold tracking-tight text-lg">
            GEO<span className="text-emerald-400"> Lab</span>
          </a>
          <nav className="flex gap-1">
            <NavLink to="/projects" label="Проекты" />
            <NavLink to="/researches" label="Исследования" />
            <NavLink to="/organization" label="Организация" />
            <NavLink to="/account" label="Аккаунт" />
            <NavLink to="/settings" label="Настройки" />
          </nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="text-slate-300">{user?.name || user?.email}</span>
            <button
              onClick={onLogout}
              className="px-2 py-1 rounded-md text-xs text-slate-300 hover:text-white hover:bg-white/5 transition-colors"
            >
              Выйти
            </button>
          </div>
        </div>
      </header>
      <main className="w-full px-4 sm:px-6 lg:px-10 py-6">{children}</main>
    </div>
  )
}

function NavLink({ to, label }) {
  return (
    <a
      href={to}
      className="px-3 py-1.5 rounded-md text-sm font-medium transition-colors text-slate-300 hover:text-white hover:bg-white/5"
    >
      {label}
    </a>
  )
}