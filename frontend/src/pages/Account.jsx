import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { btnPrimary, btnDanger, inputCls } from '../components/ui.jsx'

export default function Account() {
  const navigate = useNavigate()
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // profile form
  const [name, setName] = useState('')
  const [profileMsg, setProfileMsg] = useState('')
  const [profileErr, setProfileErr] = useState('')
  const [profileSaving, setProfileSaving] = useState(false)

  // password form
  const [curPw, setCurPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [pwMsg, setPwMsg] = useState('')
  const [pwErr, setPwErr] = useState('')
  const [pwSaving, setPwSaving] = useState(false)

  useEffect(() => {
    api
      .me()
      .then((u) => {
        setUser(u)
        setName(u.name || '')
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  async function saveProfile(e) {
    e.preventDefault()
    setProfileMsg('')
    setProfileErr('')
    setProfileSaving(true)
    try {
      const u = await api.updateProfile({ name: name || null })
      setUser(u)
      setProfileMsg('Имя обновлено')
    } catch (err) {
      setProfileErr(err.message || 'Ошибка')
    } finally {
      setProfileSaving(false)
    }
  }

  async function savePassword(e) {
    e.preventDefault()
    setPwMsg('')
    setPwErr('')
    if (newPw !== confirmPw) {
      setPwErr('Пароли не совпадают')
      return
    }
    setPwSaving(true)
    try {
      await api.changePassword({ current_password: curPw, new_password: newPw })
      setPwMsg('Пароль изменён. Выполняется выход…')
      setTimeout(() => navigate('/login', { replace: true }), 1500)
    } catch (err) {
      setPwErr(err.message || 'Ошибка при смене пароля')
    } finally {
      setPwSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="text-slate-400 text-sm flex items-center gap-2 py-4">
        <span className="inline-block w-4 h-4 border-2 border-slate-300 border-t-emerald-500 rounded-full animate-spin" />
        Загрузка…
      </div>
    )
  }

  return (
    <div className="max-w-lg mx-auto space-y-6">
      <h1 className="text-xl font-bold text-ink">Аккаунт</h1>

      {/* Profile */}
      <div className="bg-white rounded-lg border border-slate-200 p-6">
        <h2 className="text-base font-semibold text-ink mb-4">Профиль</h2>

        {profileMsg && (
          <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm rounded-md px-3 py-2 mb-3">
            {profileMsg}
          </div>
        )}
        {profileErr && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-3 py-2 mb-3">
            {profileErr}
          </div>
        )}

        <form onSubmit={saveProfile} className="space-y-3">
          <label className="block text-sm font-medium text-slate-700">
            Email
            <input
              type="text"
              value={user?.email || ''}
              disabled
              className={`${inputCls} bg-slate-100 cursor-not-allowed`}
            />
          </label>

          <label className="block text-sm font-medium text-slate-700">
            Имя
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className={inputCls}
              autoComplete="name"
            />
          </label>

          <button type="submit" disabled={profileSaving} className={btnPrimary}>
            {profileSaving ? 'Сохранение…' : 'Сохранить'}
          </button>
        </form>
      </div>

      {/* Security */}
      <div className="bg-white rounded-lg border border-slate-200 p-6">
        <h2 className="text-base font-semibold text-ink mb-4">Безопасность</h2>

        {pwMsg && (
          <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm rounded-md px-3 py-2 mb-3">
            {pwMsg}
          </div>
        )}
        {pwErr && (
          <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-md px-3 py-2 mb-3">
            {pwErr}
          </div>
        )}

        <form onSubmit={savePassword} className="space-y-3">
          <label className="block text-sm font-medium text-slate-700">
            Текущий пароль
            <input
              type="password"
              value={curPw}
              onChange={(e) => setCurPw(e.target.value)}
              required
              className={inputCls}
              autoComplete="current-password"
            />
          </label>

          <label className="block text-sm font-medium text-slate-700">
            Новый пароль
            <input
              type="password"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              required
              minLength={8}
              className={inputCls}
              autoComplete="new-password"
            />
          </label>

          <label className="block text-sm font-medium text-slate-700">
            Повторите новый пароль
            <input
              type="password"
              value={confirmPw}
              onChange={(e) => setConfirmPw(e.target.value)}
              required
              className={inputCls}
              autoComplete="new-password"
            />
          </label>

          <button type="submit" disabled={pwSaving} className={btnDanger}>
            {pwSaving ? 'Смена…' : 'Изменить пароль'}
          </button>
        </form>
      </div>
    </div>
  )
}