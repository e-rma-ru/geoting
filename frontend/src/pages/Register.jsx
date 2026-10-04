import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { inputCls, btnPrimary } from '../components/ui.jsx'

export default function Register() {
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await api.register({ name: name || undefined, email, password })
      navigate('/projects', { replace: true })
    } catch (err) {
      if (err.message && err.message.includes('Email already registered')) {
        setError('Пользователь с таким email уже зарегистрирован')
      } else if (err.message && err.message.includes('validation')) {
        setError('Проверьте правильность введённых данных')
      } else {
        setError(err.message || 'Ошибка регистрации')
      }
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
          <h2 className="text-lg font-semibold text-ink mb-1">Регистрация</h2>

          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-3 py-2">{error}</div>
          )}

          <label className="block text-sm font-medium text-slate-700 mb-1">
            Имя
            <input type="text" value={name} onChange={(e) => setName(e.target.value)} className={inputCls} autoComplete="name" placeholder="Иван Петров" />
          </label>

          <label className="block text-sm font-medium text-slate-700 mb-1">
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required className={inputCls} autoComplete="email" />
          </label>

          <label className="block text-sm font-medium text-slate-700 mb-1">
            Пароль
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} className={inputCls} autoComplete="new-password" />
          </label>

          <button type="submit" disabled={loading} className={`${btnPrimary} w-full justify-center`}>
            {loading ? 'Регистрация…' : 'Зарегистрироваться'}
          </button>

          <p className="text-center text-sm text-slate-500">
            Уже есть аккаунт?{' '}
            <Link to="/login" className="text-emerald-600 hover:text-emerald-700 font-medium">
              Войти
            </Link>
          </p>
        </form>
      </div>
    </div>
  )
}