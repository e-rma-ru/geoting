import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { inputCls, btnPrimary } from '../components/ui.jsx'

export default function Login() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await api.login({ email, password })
      navigate('/projects', { replace: true })
    } catch (err) {
      setError('Неверный email или пароль')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="w-full max-w-sm mx-4">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-ink">GEO<span className="text-emerald-500"> Lab</span></h1>
        </div>

        <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 space-y-4">
          <h2 className="text-lg font-semibold text-ink mb-1">Вход</h2>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-3 py-2">{error}</div>
          )}

          <label className="block text-sm font-medium text-slate-700 mb-1">
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className={inputCls} autoComplete="email" />
          </label>

          <label className="block text-sm font-medium text-slate-700 mb-1">
            Пароль
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required className={inputCls} autoComplete="current-password" />
          </label>

          <button type="submit" disabled={loading} className={`${btnPrimary} w-full justify-center`}>
            {loading ? 'Вход…' : 'Войти'}
          </button>

          <p className="text-center text-sm text-slate-500">
            Нет аккаунта?{' '}
            <Link to="/register" className="text-emerald-600 hover:text-emerald-700 font-medium">
              Зарегистрироваться
            </Link>
          </p>
        </form>
      </div>
    </div>
  )
}