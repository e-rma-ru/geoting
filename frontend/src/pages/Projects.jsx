import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { fmt } from '../i18n.js'
import { btnPrimary, btnSecondary, EmptyState, inputCls, Modal, Spinner, fmtDate } from '../components/ui.jsx'

export default function Projects() {
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [form, setForm] = useState({ name: '', city: '', website: '', category: '', description: '' })

  async function load() {
    try {
      setError('')
      const data = await api.projects()
      setProjects(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function create() {
    if (!form.name.trim()) return
    try {
      await api.createProject({
        name: form.name.trim(),
        city: form.city.trim() || null,
        website: form.website.trim() || null,
        category: form.category.trim() || null,
        description: form.description.trim() || null,
        brand_aliases: [],
        competitors: [],
      })
      setShowCreate(false)
      setForm({ name: '', city: '', website: '', category: '', description: '' })
      setLoading(true)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">{fmt('projects.title')}</h1>
        <button className={btnPrimary} onClick={() => setShowCreate(true)}>
          {fmt('projects.create')}
        </button>
      </div>

      {error && <div className="mb-4 rounded-md bg-red-50 border border-red-200 text-red-700 px-3 py-2 text-sm">{error}</div>}

      {loading ? (
        <Spinner label={fmt('common.loading')} />
      ) : projects.length === 0 ? (
        <EmptyState title={fmt('projects.emptyTitle')} hint={fmt('projects.emptyHint')} />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((p) => (
            <Link
              key={p.id}
              to={`/projects/${p.id}`}
              className="bg-white rounded-xl border border-slate-200 p-5 hover:shadow-md hover:border-emerald-300 transition-shadow"
            >
              <div className="font-semibold text-lg">{p.name}</div>
              <div className="text-sm text-slate-500 mt-0.5">
                {[p.city, p.category].filter(Boolean).join(' · ') || '—'}
              </div>
              <div className="mt-4 grid grid-cols-3 gap-2 text-center">
                <div className="bg-slate-50 rounded-md py-2">
                  <div className="text-lg font-bold mono">{p.active_prompts}</div>
                  <div className="text-[11px] text-slate-500">{fmt('projects.prompts')}</div>
                </div>
                <div className="bg-slate-50 rounded-md py-2">
                  <div className="text-lg font-bold mono">{p.researches_count}</div>
                  <div className="text-[11px] text-slate-500">{fmt('projects.researches')}</div>
                </div>
                <div className="bg-slate-50 rounded-md py-2">
                  <div className="text-lg font-bold mono">{p.last_research_at ? fmtDate(p.last_research_at) : '—'}</div>
                  <div className="text-[11px] text-slate-500">{fmt('projects.lastResearch')}</div>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      <Modal open={showCreate} onClose={() => setShowCreate(false)} title={fmt('projects.new')}>
        <div className="space-y-3">
          <div>
            <label className="text-sm font-medium block mb-1">{fmt('projects.name')} *</label>
            <input className={inputCls} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder={fmt('projects.name')} />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium block mb-1">{fmt('projects.city')}</label>
              <input className={inputCls} value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} />
            </div>
            <div>
              <label className="text-sm font-medium block mb-1">{fmt('projects.category')}</label>
              <input className={inputCls} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium block mb-1">{fmt('projects.website')}</label>
            <input className={inputCls} value={form.website} onChange={(e) => setForm({ ...form, website: e.target.value })} placeholder="https://…" />
          </div>
          <div>
            <label className="text-sm font-medium block mb-1">{fmt('projects.description')}</label>
            <textarea className={inputCls} rows={3} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <button className={btnSecondary} onClick={() => setShowCreate(false)}>
              {fmt('common.cancel')}
            </button>
            <button className={btnPrimary} onClick={create} disabled={!form.name.trim()}>
              {fmt('common.create')}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}
