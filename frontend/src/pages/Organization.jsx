import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { btnPrimary, btnSecondary, btnDanger, inputCls, Modal } from '../components/ui.jsx'

export default function OrganizationPage() {
  const [org, setOrg] = useState(null)
  const [members, setMembers] = useState([])
  const [invites, setInvites] = useState([])
  const [loading, setLoading] = useState(true)

  // org edit
  const [orgName, setOrgName] = useState('')
  const [orgMsg, setOrgMsg] = useState('')
  const [orgSaving, setOrgSaving] = useState(false)

  // invite
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('MEMBER')
  const [inviteResult, setInviteResult] = useState('')
  const [inviteSaving, setInviteSaving] = useState(false)

  // transfer
  const [showTransfer, setShowTransfer] = useState(false)
  const [transferUserId, setTransferUserId] = useState('')
  const [transferMsg, setTransferMsg] = useState('')

  const role = org?.role

  async function load() {
    setLoading(true)
    try {
      const [o, m, iv] = await Promise.all([
        api.getOrganization(),
        api.listMembers(),
        role === 'OWNER' || role === 'ADMIN' ? api.listInvites().catch(() => []) : Promise.resolve([]),
      ])
      setOrg(o)
      setOrgName(o.name)
      setMembers(m)
      setInvites(iv)
    } catch {}
    setLoading(false)
  }

  useEffect(() => { if (role) load() }, [role])

  useEffect(() => { load() }, [])

  async function saveOrg(e) {
    e.preventDefault()
    setOrgMsg('')
    setOrgSaving(true)
    try {
      const o = await api.updateOrganization({ name: orgName })
      setOrg(o)
      setOrgMsg('Сохранено')
    } catch (err) {
      setOrgMsg(err.message)
    }
    setOrgSaving(false)
  }

  async function changeRole(membershipId, newRole) {
    try {
      await api.updateMemberRole(membershipId, { role: newRole })
      await load()
    } catch (err) {
      alert(err.message)
    }
  }

  async function removeMember(membershipId) {
    if (!confirm('Удалить участника из организации?')) return
    try {
      await api.deleteMember(membershipId)
      await load()
    } catch (err) {
      alert(err.message)
    }
  }

  async function sendInvite(e) {
    e.preventDefault()
    setInviteResult('')
    setInviteSaving(true)
    try {
      const inv = await api.createInvite({ email: inviteEmail, role: inviteRole })
      setInviteResult(`Приглашение создано. Токен: ${inv.token}`)
      setInviteEmail('')
      setInviteRole('MEMBER')
      await load()
    } catch (err) {
      setInviteResult(`Ошибка: ${err.message}`)
    }
    setInviteSaving(false)
  }

  async function transferOwnership() {
    setTransferMsg('')
    try {
      await api.transferOwnership({ user_id: parseInt(transferUserId, 10) })
      setTransferMsg('Права владельца переданы')
      setShowTransfer(false)
      await load()
    } catch (err) {
      setTransferMsg(err.message)
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

  const roleLabel = role === 'OWNER' ? 'Владелец' : role === 'ADMIN' ? 'Администратор' : 'Участник'
  const isAdmin = role === 'OWNER' || role === 'ADMIN'

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-xl font-bold text-ink">Организация</h1>

      {/* Organization info */}
      <div className="bg-white rounded-lg border border-slate-200 p-6">
        {role === 'OWNER' ? (
          <form onSubmit={saveOrg} className="space-y-3">
            {orgMsg && <div className="bg-emerald-50 border border-emerald-200 text-emerald-700 text-sm rounded-md px-3 py-2">{orgMsg}</div>}
            <label className="block text-sm font-medium text-slate-700">
              Название
              <input type="text" value={orgName} onChange={(e) => setOrgName(e.target.value)} className={inputCls} />
            </label>
            <button type="submit" disabled={orgSaving} className={btnPrimary}>{orgSaving ? 'Сохранение…' : 'Сохранить'}</button>
          </form>
        ) : (
          <div>
            <div className="text-sm text-slate-500 mb-1">Название</div>
            <div className="font-medium">{org?.name}</div>
          </div>
        )}
        <div className="mt-3">
          <div className="text-sm text-slate-500 mb-1">Slug</div>
          <div className="font-mono text-sm">{org?.slug}</div>
        </div>
        <div className="mt-3">
          <div className="text-sm text-slate-500 mb-1">Моя роль</div>
          <div className="font-medium">{roleLabel}</div>
        </div>
      </div>

      {/* Members */}
      <div className="bg-white rounded-lg border border-slate-200 p-6">
        <h2 className="text-base font-semibold text-ink mb-4">Участники</h2>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-slate-500 border-b border-slate-200">
              <th className="pb-2 font-medium">Имя</th>
              <th className="pb-2 font-medium">Email</th>
              <th className="pb-2 font-medium">Роль</th>
              {(role === 'OWNER' || role === 'ADMIN') && <th className="pb-2 font-medium">Действия</th>}
            </tr>
          </thead>
          <tbody>
            {members.map((m) => (
              <tr key={m.id} className="border-b border-slate-100 last:border-0">
                <td className="py-2">{m.name || '—'}</td>
                <td className="py-2">{m.email}</td>
                <td className="py-2">
                  {role === 'OWNER' && m.role !== 'OWNER' ? (
                    <select
                      value={m.role}
                      onChange={(e) => changeRole(m.id, e.target.value)}
                      className="text-sm border border-slate-300 rounded px-1 py-0.5"
                    >
                      <option value="ADMIN">ADMIN</option>
                      <option value="MEMBER">MEMBER</option>
                    </select>
                  ) : role === 'ADMIN' && m.role === 'MEMBER' ? (
                    <select
                      value={m.role}
                      onChange={(e) => changeRole(m.id, e.target.value)}
                      className="text-sm border border-slate-300 rounded px-1 py-0.5"
                    >
                      <option value="MEMBER">MEMBER</option>
                      <option value="ADMIN">ADMIN</option>
                    </select>
                  ) : (
                    <span>{m.role === 'OWNER' ? 'Владелец' : m.role === 'ADMIN' ? 'Администратор' : 'Участник'}</span>
                  )}
                </td>
                {(role === 'OWNER' || role === 'ADMIN') && (
                  <td className="py-2">
                    {m.role !== 'OWNER' && (
                      <>
                        {(role === 'OWNER' || (role === 'ADMIN' && m.role === 'MEMBER')) && (
                          <button onClick={() => removeMember(m.id)} className="text-red-500 hover:text-red-700 text-xs font-medium">
                            Удалить
                          </button>
                        )}
                      </>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Transfer ownership (OWNER only) */}
      {role === 'OWNER' && (
        <div className="bg-white rounded-lg border border-slate-200 p-6">
          <h2 className="text-base font-semibold text-ink mb-4">Передать права владельца</h2>
          <div className="flex gap-2 items-center">
            <input
              type="number"
              placeholder="ID участника"
              value={transferUserId}
              onChange={(e) => setTransferUserId(e.target.value)}
              className={`${inputCls} w-32`}
            />
            <button onClick={() => setShowTransfer(true)} className={btnDanger}>Передать</button>
          </div>
          <Modal open={showTransfer} onClose={() => setShowTransfer(false)} title="Передать права владельца?">
            <p className="text-sm text-slate-600 mb-4">Вы станете администратором. Новый владелец получит полный контроль над организацией.</p>
            {transferMsg && <div className="text-sm mb-2 text-red-600">{transferMsg}</div>}
            <div className="flex gap-2 justify-end">
              <button onClick={() => setShowTransfer(false)} className={btnSecondary}>Отмена</button>
              <button onClick={transferOwnership} className={btnDanger}>Подтвердить</button>
            </div>
          </Modal>
        </div>
      )}

      {/* Invite */}
      {isAdmin && (
        <div className="bg-white rounded-lg border border-slate-200 p-6">
          <h2 className="text-base font-semibold text-ink mb-4">Пригласить участника</h2>
          <form onSubmit={sendInvite} className="space-y-3">
            {inviteResult && (
              <div className="bg-slate-50 border border-slate-200 text-sm rounded-md px-3 py-2 break-all">{inviteResult}</div>
            )}
            <label className="block text-sm font-medium text-slate-700">
              Email
              <input type="email" value={inviteEmail} onChange={(e) => setInviteEmail(e.target.value)} required className={inputCls} />
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Роль
              <select value={inviteRole} onChange={(e) => setInviteRole(e.target.value)} className={inputCls}>
                {role === 'OWNER' && <option value="ADMIN">Администратор</option>}
                <option value="MEMBER">Участник</option>
              </select>
            </label>
            <button type="submit" disabled={inviteSaving} className={btnPrimary}>
              {inviteSaving ? 'Отправка…' : 'Пригласить'}
            </button>
          </form>
        </div>
      )}
    </div>
  )
}