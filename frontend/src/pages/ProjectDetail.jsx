import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api.js'
import { fmt } from '../i18n.js'
import {
  btnDanger, btnPrimary, btnSecondary, CLUSTERS, clusterLabel, EmptyState, fmtDate, fmtNum, intentLabel,
  inputCls, Modal, pct, Spinner, StatusBadge, TableScroll,
} from '../components/ui.jsx'

export default function ProjectDetail() {
  const { projectId } = useParams()
  const [project, setProject] = useState(null)
  const [researches, setResearches] = useState([])
  const [prompts, setPrompts] = useState([])
  const [metricsByResearch, setMetricsByResearch] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('research')

  // run research modal
  const [showRun, setShowRun] = useState(false)
  const [runForm, setRunForm] = useState({ models: [], runs: 3, name: '' })
  const [starting, setStarting] = useState(false)
  const [modelOptions, setModelOptions] = useState([])
  const [modelSearch, setModelSearch] = useState('')
  const [defaultModel, setDefaultModel] = useState('')

  // compare
  const [compareIds, setCompareIds] = useState([])

  // delete research
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [toast, setToast] = useState('')

  // prompts
  const [promptFilter, setPromptFilter] = useState({ cluster: '', active: '' })
  const [newPrompt, setNewPrompt] = useState({ text: '', cluster: 'discovery', intent: 'commercial' })
  const [editPrompt, setEditPrompt] = useState(null)
  const [importMsg, setImportMsg] = useState('')
  const [editingProject, setEditingProject] = useState(false)
  const [projForm, setProjForm] = useState(null)

  const load = useCallback(async () => {
    try {
      setError('')
      const [p, r, pr] = await Promise.all([
        api.getProject(projectId),
        api.researches(projectId),
        api.prompts(projectId),
      ])
      setProject(p)
      setResearches(r)
      setPrompts(pr)
      const mm = {}
      for (const res of r) {
        try {
          mm[res.id] = await api.researchMetrics?.(res.id)
        } catch {
          mm[res.id] = null
        }
      }
      setMetricsByResearch(mm)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [projectId])

  useEffect(() => {
    load()
  }, [load])

  // Poll active research status
  const active = useMemo(() => researches.find((r) => r.status === 'running' || r.status === 'queued'), [researches])
  useEffect(() => {
    if (!active) return
    const t = setInterval(() => load(), 4000)
    return () => clearInterval(t)
  }, [active, load])

  async function startResearch() {
    if (!runForm.models.length) return
    setStarting(true)
    setError('')
    try {
      await api.createResearch({
        project_id: Number(projectId),
        name: runForm.name.trim() || null,
        models: runForm.models,
        runs_per_prompt: Number(runForm.runs),
      })
      setShowRun(false)
      setRunForm({ models: [], runs: 3, name: '' })
      await load()
    } catch (e) {
      setError(e.message)
    } finally {
      setStarting(false)
    }
  }

  async function openRunModal() {
    setError('')
    setShowRun(true)
    setModelSearch('')
    if (modelOptions.length) {
      if (!runForm.models.length) setRunForm((f) => ({ ...f, models: defaultModel ? [defaultModel] : [] }))
      return
    }
    try {
      const [m, s] = await Promise.all([api.models(), api.settings()])
      const models = m.models || []
      const def = s?.routerai?.default_model || ''
      setModelOptions(models)
      setDefaultModel(def)
      setRunForm((f) => ({ ...f, models: f.models.length ? f.models : def ? [def] : [] }))
    } catch (e) {
      setError(e.message)
    }
  }

  function toggleModel(modelId) {
    setRunForm((f) => ({
      ...f,
      models: f.models.includes(modelId) ? f.models.filter((m) => m !== modelId) : [...f.models, modelId],
    }))
  }

  const visibleModels = useMemo(() => {
    const q = modelSearch.trim().toLowerCase()
    if (!q) return modelOptions
    return modelOptions.filter((m) => m.id.toLowerCase().includes(q) || (m.name || '').toLowerCase().includes(q))
  }, [modelOptions, modelSearch])

  const runSummary = useMemo(() => {
    const promptsN = prompts.filter((p) => p.active).length
    const modelsN = runForm.models.length
    const runsN = Number(runForm.runs || 0)
    return { prompts: promptsN, models: modelsN, runs: runsN, total: promptsN * modelsN * runsN }
  }, [prompts, runForm.models, runForm.runs])

  async function confirmDeleteResearch() {
    if (!deleteTarget) return
    setDeleting(true)
    setError('')
    try {
      await api.deleteResearch(deleteTarget.id)
      setResearches((prev) => prev.filter((r) => r.id !== deleteTarget.id))
      setDeleteTarget(null)
      setToast(fmt('research.deleteSuccess'))
      setTimeout(() => setToast(''), 3000)
    } catch (e) {
      setError(`${fmt('research.deleteError')}: ${e.message}`)
    } finally {
      setDeleting(false)
    }
  }

  async function togglePrompt(p) {
    try {
      await api.updatePrompt(p.id, { active: !p.active })
      setPrompts((prev) => prev.map((x) => (x.id === p.id ? { ...x, active: !p.active } : x)))
    } catch (e) {
      setError(e.message)
    }
  }

  async function addPrompt() {
    if (!newPrompt.text.trim()) return
    try {
      const created = await api.createPrompt(projectId, { ...newPrompt, text: newPrompt.text.trim() })
      setPrompts((prev) => [...prev, created])
      setNewPrompt({ text: '', cluster: 'discovery', intent: 'commercial' })
    } catch (e) {
      setError(e.message)
    }
  }

  async function saveEditPrompt() {
    try {
      const updated = await api.updatePrompt(editPrompt.id, editPrompt)
      setPrompts((prev) => prev.map((x) => (x.id === updated.id ? updated : x)))
      setEditPrompt(null)
    } catch (e) {
      setError(e.message)
    }
  }

  async function removePrompt(p) {
    if (!window.confirm(fmt('prompts.deleteConfirm'))) return
    try {
      await api.deletePrompt(p.id)
      setPrompts((prev) => prev.filter((x) => x.id !== p.id))
    } catch (e) {
      setError(e.message)
    }
  }

  async function importCsv(file) {
    if (!file) return
    try {
      const res = await api.importPromptsCsv(projectId, file)
      setImportMsg(fmt('prompts.importResult', { created: res.created, skipped: res.skipped }))
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  async function saveProject() {
    try {
      const payload = { ...projForm }
      for (const k of Object.keys(payload)) {
        if (typeof payload[k] === 'string') payload[k] = payload[k].trim() || null
      }
      payload.brand_aliases = projForm.brand_aliases
        .split('\n').map((s) => s.trim()).filter(Boolean)
      payload.competitors = projForm.competitors
        .split('\n').map((s) => s.trim()).filter(Boolean)
      await api.updateProject(projectId, payload)
      setEditingProject(false)
      await load()
    } catch (e) {
      setError(e.message)
    }
  }

  const filteredPrompts = useMemo(() => {
    return prompts.filter((p) => {
      if (promptFilter.cluster && p.cluster !== promptFilter.cluster) return false
      if (promptFilter.active === 'true' && !p.active) return false
      if (promptFilter.active === 'false' && p.active) return false
      return true
    })
  }, [prompts, promptFilter])

  if (loading) return <Spinner label={fmt('projects.loading')} />
  if (!project) return <EmptyState title={fmt('projects.notFound')} />

  const m = (rid) => metricsByResearch[rid]

  return (
    <div>
      {error && <div className="mb-4 rounded-md bg-red-50 border border-red-200 text-red-700 px-3 py-2 text-sm">{error}</div>}

      {/* Project header */}
      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-4">
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-bold">{project.name}</h1>
            <div className="text-sm text-slate-500 mt-1">
              {[project.city, project.country, project.category].filter(Boolean).join(' · ')}
              {project.website && <a className="ml-2 text-emerald-600 hover:underline" href={project.website} target="_blank" rel="noreferrer">{project.website}</a>}
            </div>
            {project.description && <p className="text-sm text-slate-600 mt-2">{project.description}</p>}
            <div className="flex flex-wrap gap-1.5 mt-3">
              {(project.brand_aliases || []).map((a) => (
                <span key={a} className="text-xs bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-full px-2 py-0.5">{a}</span>
              ))}
            </div>
          </div>
          <div className="flex gap-2">
            <button className={btnSecondary} onClick={() => {
              setProjForm({
                name: project.name, website: project.website || '', city: project.city || '',
                country: project.country || '', category: project.category || '',
                description: project.description || '', target_audience: project.target_audience || '',
                services: project.services || '',
                brand_aliases: (project.brand_aliases || []).join('\n'),
                competitors: (project.competitors || []).join('\n'),
              })
              setEditingProject(true)
            }}>
              {fmt('common.edit')}
            </button>
            <button className={btnPrimary} onClick={openRunModal}>{fmt('research.run')}</button>
          </div>
        </div>
      </div>

      {active && (
        <div className="mb-4 rounded-lg bg-blue-50 border border-blue-200 text-blue-800 px-4 py-3 text-sm flex items-center justify-between">
          <span>
            <span className="inline-block w-3 h-3 border-2 border-blue-300 border-t-blue-600 rounded-full animate-spin mr-2" />
            {fmt('research.runningNotice', { name: active.name, status: active.status })}
          </span>
          <Link to={`/projects/${projectId}/research/${active.id}`} className="underline">{fmt('research.open')}</Link>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-1 mb-4">
        {[
          { id: 'research', label: fmt('research.title') },
          { id: 'prompts', label: `${fmt('prompts.title')} (${prompts.length})` },
        ].map((tb) => (
          <button
            key={tb.id}
            onClick={() => setTab(tb.id)}
            className={`px-4 py-2 rounded-t-lg text-sm font-medium ${
              tab === tb.id ? 'bg-white border border-b-0 border-slate-200 text-ink' : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            {tb.label}
          </button>
        ))}
      </div>

      {tab === 'research' && (
        <div>
          {researches.length === 0 ? (
            <EmptyState title={fmt('research.emptyTitle')} hint={fmt('research.emptyHint')} />
          ) : (
            <div className="bg-white rounded-lg border border-slate-200">
              <TableScroll>
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-4 py-2 w-8">
                        <input
                          type="checkbox"
                        onChange={(e) => {
                          const checked = e.target.checked
                          setCompareIds(checked ? researches.filter((r) => r.status === 'completed').map((r) => r.id) : [])
                        }}
                      />
                    </th>
                    <th className="px-4 py-2">{fmt('research.research')}</th>
                    <th className="px-4 py-2">{fmt('research.status')}</th>
                    <th className="px-4 py-2 text-right">{fmt('metrics.mention_rate')}</th>
                    <th className="px-4 py-2 text-right">{fmt('metrics.top3_rate')}</th>
                    <th className="px-4 py-2 text-right">{fmt('metrics.average_position')}</th>
                    <th className="px-4 py-2 text-right">{fmt('metrics.recommendation_rate')}</th>
                    <th className="px-4 py-2 text-right">{fmt('metrics.citation_rate')}</th>
                    <th className="px-4 py-2 text-right">{fmt('metrics.entity_accuracy')}</th>
                    <th className="px-4 py-2">{fmt('research.created')}</th>
                    <th className="px-4 py-2 w-24 text-right">{fmt('common.actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {researches.map((r) => {
                    const mm = m(r.id)
                    return (
                      <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50">
                        <td className="px-4 py-2">
                          <input
                            type="checkbox"
                            checked={compareIds.includes(r.id)}
                            disabled={r.status !== 'completed'}
                            onChange={(e) =>
                              setCompareIds((prev) => (e.target.checked ? [...prev, r.id] : prev.filter((x) => x !== r.id)))
                            }
                          />
                        </td>
                        <td className="px-4 py-2">
                          <Link to={`/projects/${projectId}/research/${r.id}`} className="font-medium text-emerald-700 hover:underline">
                            {r.name}
                          </Link>
                          <div className="text-xs text-slate-400">
                            {(r.models && r.models.length ? r.models : [fmt('research.noModel')]).map((m) => (
                              <span key={m} className="inline-block bg-slate-100 border border-slate-200 rounded-full px-1.5 py-0.5 mr-1 mb-0.5 mono">{m}</span>
                            ))}
                          </div>
                          <div className="text-xs text-slate-400">
                            {fmt('research.dimensions', { prompts: r.prompts_count, providers: r.models?.length ?? r.providers_count, runs: r.runs_per_prompt })}
                          </div>
                        </td>
                        <td className="px-4 py-2"><StatusBadge status={r.status} /></td>
                        <td className="px-4 py-2 text-right mono">{pct(mm?.mention_rate)}</td>
                        <td className="px-4 py-2 text-right mono">{pct(mm?.top3_rate)}</td>
                        <td className="px-4 py-2 text-right mono">{fmtNum(mm?.average_position)}</td>
                        <td className="px-4 py-2 text-right mono">{pct(mm?.recommendation_rate)}</td>
                        <td className="px-4 py-2 text-right mono">{pct(mm?.citation_rate)}</td>
                        <td className="px-4 py-2 text-right mono">{fmtNum(mm?.entity_accuracy, 0)}</td>
                        <td className="px-4 py-2 text-slate-500">{fmtDate(r.created_at)}</td>
                        <td className="px-4 py-2">
                          <div className="flex justify-end">
                            <button
                              className="inline-flex items-center rounded-md border border-red-200 bg-white px-2 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
                              onClick={() => setDeleteTarget(r)}
                            >
                              {fmt('research.delete')}
                            </button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              </TableScroll>
              {compareIds.length >= 2 && (
                <div className="p-3 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
                  <span className="text-sm text-slate-600">{fmt('research.compareSelected', { count: compareIds.length })}</span>
                  <Link
                    className={btnPrimary}
                    to={`/projects/${projectId}/research/${compareIds[0]}?compare=${compareIds.slice(1).join(',')}`}
                  >
                    {fmt('research.compare')}
                  </Link>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {tab === 'prompts' && (
        <div className="space-y-4">
          {/* filters + import */}
          <div className="bg-white rounded-lg border border-slate-200 p-4 flex flex-wrap gap-3 items-end">
            <div>
              <label className="text-xs font-medium text-slate-500 block mb-1">{fmt('prompts.filterCluster')}</label>
              <select className={inputCls + ' w-44'} value={promptFilter.cluster} onChange={(e) => setPromptFilter({ ...promptFilter, cluster: e.target.value })}>
                <option value="">{fmt('dashboard.filterAll')}</option>
                {CLUSTERS.map((c) => <option key={c} value={c}>{clusterLabel(c)}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500 block mb-1">{fmt('prompts.filterStatus')}</label>
              <select className={inputCls + ' w-32'} value={promptFilter.active} onChange={(e) => setPromptFilter({ ...promptFilter, active: e.target.value })}>
                <option value="">{fmt('dashboard.filterAll')}</option>
                <option value="true">{fmt('prompts.active')}</option>
                <option value="false">{fmt('prompts.inactive')}</option>
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-slate-500 block mb-1">{fmt('prompts.importCsv')}</label>
              <input
                type="file"
                accept=".csv"
                className="text-sm"
                onChange={(e) => importCsv(e.target.files[0])}
              />
            </div>
            <a className={btnSecondary} href={api.exportPromptsCsvUrl(projectId)}>{fmt('prompts.exportCsv')}</a>
            {importMsg && <span className="text-sm text-emerald-700">{importMsg}</span>}
          </div>

          {/* add prompt */}
          <div className="bg-white rounded-lg border border-slate-200 p-4 flex gap-2 items-center">
            <input
              className={inputCls}
              placeholder={fmt('prompts.placeholder')}
              value={newPrompt.text}
              onChange={(e) => setNewPrompt({ ...newPrompt, text: e.target.value })}
              onKeyDown={(e) => e.key === 'Enter' && addPrompt()}
            />
            <select className={inputCls + ' w-36'} value={newPrompt.cluster} onChange={(e) => setNewPrompt({ ...newPrompt, cluster: e.target.value })}>
              {CLUSTERS.map((c) => <option key={c} value={c}>{clusterLabel(c)}</option>)}
            </select>
            <button className={btnPrimary} onClick={addPrompt} disabled={!newPrompt.text.trim()}>{fmt('common.add')}</button>
          </div>

          {filteredPrompts.length === 0 ? (
            <EmptyState title={fmt('prompts.emptyTitle')} hint={fmt('prompts.emptyHint')} />
          ) : (
            <div className="bg-white rounded-lg border border-slate-200">
              <TableScroll>
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-4 py-2">{fmt('prompts.text')}</th>
                      <th className="px-4 py-2 w-28">{fmt('prompts.cluster')}</th>
                      <th className="px-4 py-2 w-28">{fmt('prompts.intent')}</th>
                      <th className="px-4 py-2 w-24">{fmt('prompts.active')}</th>
                      <th className="px-4 py-2 w-32 text-right">{fmt('common.actions')}</th>
                    </tr>
                  </thead>
                <tbody>
                  {filteredPrompts.map((p) => (
                    <tr key={p.id} className="border-t border-slate-100 hover:bg-slate-50">
                      <td className="px-4 py-2">{p.text}</td>
                      <td className="px-4 py-2">
                        <span className="text-xs bg-slate-100 border border-slate-200 rounded-full px-2 py-0.5">{clusterLabel(p.cluster) || '—'}</span>
                      </td>
                      <td className="px-4 py-2 text-slate-500">{intentLabel(p.intent) || '—'}</td>
                      <td className="px-4 py-2">
                        <button
                          onClick={() => togglePrompt(p)}
                          className={`relative w-10 h-5 rounded-full transition-colors ${p.active ? 'bg-emerald-500' : 'bg-slate-300'}`}
                          title={p.active ? fmt('prompts.deactivate') : fmt('prompts.activate')}
                        >
                          <span className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-all ${p.active ? 'left-5' : 'left-0.5'}`} />
                        </button>
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex justify-end gap-1">
                          <button className={btnSecondary + ' !px-2 !py-1'} onClick={() => setEditPrompt(p)}>{fmt('common.edit')}</button>
                          <button className={btnDanger + ' !px-2 !py-1'} onClick={() => removePrompt(p)}>{fmt('prompts.deleted')}</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              </TableScroll>
            </div>
          )}
        </div>
      )}

      {/* Run research modal */}
      <Modal open={showRun} onClose={() => setShowRun(false)} title={fmt('research.run')}>
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium block mb-1">{fmt('research.name')}</label>
            <input className={inputCls} placeholder="Базовый замер" value={runForm.name} onChange={(e) => setRunForm({ ...runForm, name: e.target.value })} />
          </div>
          <div>
            <label className="text-sm font-medium block mb-1">{fmt('research.models')} *</label>
            <div className="border border-slate-300 rounded-md overflow-hidden">
              <input
                className="w-full px-3 py-2 text-sm focus:outline-none border-b border-slate-200"
                placeholder={fmt('research.searchModel')}
                value={modelSearch}
                onChange={(e) => setModelSearch(e.target.value)}
              />
              <div className="max-h-56 overflow-y-auto">
                {visibleModels.length === 0 && (
                  <div className="px-3 py-4 text-sm text-slate-400 text-center">{fmt('research.noModelsFound')}</div>
                )}
                {visibleModels.map((m) => (
                  <label
                    key={m.id}
                    className="flex items-center gap-2 px-3 py-1.5 text-sm cursor-pointer hover:bg-slate-50"
                  >
                    <input
                      type="checkbox"
                      className="accent-emerald-600"
                      checked={runForm.models.includes(m.id)}
                      onChange={() => toggleModel(m.id)}
                    />
                    <span className="font-medium">{m.id}</span>
                    {m.name && m.name !== m.id && <span className="text-slate-400 text-xs truncate">{m.name}</span>}
                  </label>
                ))}
              </div>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              {fmt('research.modelHint')} · {fmt('research.selected', { count: runForm.models.length })}
            </p>
          </div>
          <div>
            <label className="text-sm font-medium block mb-1">{fmt('research.runsPerPrompt')} *</label>
            <input
              type="number"
              min={1}
              max={10}
              className={inputCls + ' w-24'}
              value={runForm.runs}
              onChange={(e) => setRunForm({ ...runForm, runs: e.target.value })}
            />
          </div>
          <p className="text-xs text-slate-500">
            {fmt('research.runsHint')}{' '}
            {fmt('research.summary', {
              prompts: runSummary.prompts,
              models: runSummary.models,
              runs: runSummary.runs,
            })}
          </p>
          <div className="rounded-md bg-slate-50 border border-slate-200 px-3 py-2 text-sm text-slate-700">
            {fmt('research.totalRuns')}: <b className="mono">{runSummary.total}</b>
            {' · '}{fmt('research.apiRequests', { count: runSummary.total })}
          </div>
          <div className="rounded-md bg-amber-50 border border-amber-200 text-amber-800 px-3 py-2 text-xs">
            {fmt('research.costWarning')}
          </div>
          {error && <div className="rounded-md bg-red-50 border border-red-200 text-red-700 px-3 py-2 text-sm">{error}</div>}
          <div className="flex justify-end gap-2">
            <button className={btnSecondary} onClick={() => setShowRun(false)}>{fmt('common.cancel')}</button>
            <button className={btnPrimary} onClick={startResearch} disabled={starting || !runForm.models.length || !Number(runForm.runs)}>
              {starting ? fmt('research.starting') : fmt('research.start')}
            </button>
          </div>
        </div>
      </Modal>

      {/* Edit project modal */}
      <Modal open={editingProject} onClose={() => setEditingProject(false)} title={fmt('projects.edit')}>
        {projForm && (
          <div className="space-y-3">
            <div><label className="text-sm font-medium block mb-1">{fmt('projects.name')} *</label><input className={inputCls} value={projForm.name} onChange={(e) => setProjForm({ ...projForm, name: e.target.value })} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-sm font-medium block mb-1">{fmt('projects.city')}</label><input className={inputCls} value={projForm.city} onChange={(e) => setProjForm({ ...projForm, city: e.target.value })} /></div>
              <div><label className="text-sm font-medium block mb-1">{fmt('projects.country')}</label><input className={inputCls} value={projForm.country} onChange={(e) => setProjForm({ ...projForm, country: e.target.value })} /></div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div><label className="text-sm font-medium block mb-1">{fmt('projects.website')}</label><input className={inputCls} value={projForm.website} onChange={(e) => setProjForm({ ...projForm, website: e.target.value })} /></div>
              <div><label className="text-sm font-medium block mb-1">{fmt('projects.category')}</label><input className={inputCls} value={projForm.category} onChange={(e) => setProjForm({ ...projForm, category: e.target.value })} /></div>
            </div>
            <div><label className="text-sm font-medium block mb-1">{fmt('projects.description')}</label><textarea className={inputCls} rows={2} value={projForm.description} onChange={(e) => setProjForm({ ...projForm, description: e.target.value })} /></div>
            <div><label className="text-sm font-medium block mb-1">{fmt('projects.brandAliases')}</label><textarea className={inputCls} rows={3} value={projForm.brand_aliases} onChange={(e) => setProjForm({ ...projForm, brand_aliases: e.target.value })} /></div>
            <div><label className="text-sm font-medium block mb-1">{fmt('projects.competitors')}</label><textarea className={inputCls} rows={3} value={projForm.competitors} onChange={(e) => setProjForm({ ...projForm, competitors: e.target.value })} /></div>
            <div className="flex justify-end gap-2 pt-2">
              <button className={btnSecondary} onClick={() => setEditingProject(false)}>{fmt('common.cancel')}</button>
              <button className={btnPrimary} onClick={saveProject}>{fmt('common.save')}</button>
            </div>
          </div>
        )}
      </Modal>

      {/* Edit prompt modal */}
      <Modal open={!!editPrompt} onClose={() => setEditPrompt(null)} title={fmt('prompts.edit')}>
        {editPrompt && (
          <div className="space-y-3">
            <div><label className="text-sm font-medium block mb-1">{fmt('prompts.text')}</label><textarea className={inputCls} rows={3} value={editPrompt.text} onChange={(e) => setEditPrompt({ ...editPrompt, text: e.target.value })} /></div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-sm font-medium block mb-1">{fmt('prompts.cluster')}</label>
                <select className={inputCls} value={editPrompt.cluster || ''} onChange={(e) => setEditPrompt({ ...editPrompt, cluster: e.target.value })}>
                  <option value="">—</option>
                  {CLUSTERS.map((c) => <option key={c} value={c}>{clusterLabel(c)}</option>)}
                </select>
              </div>
              <div><label className="text-sm font-medium block mb-1">{fmt('prompts.intent')}</label><input className={inputCls} value={editPrompt.intent || ''} onChange={(e) => setEditPrompt({ ...editPrompt, intent: e.target.value })} /></div>
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button className={btnSecondary} onClick={() => setEditPrompt(null)}>{fmt('common.cancel')}</button>
              <button className={btnPrimary} onClick={saveEditPrompt}>{fmt('common.save')}</button>
            </div>
          </div>
        )}
      </Modal>

      {/* Delete research modal */}
      <Modal open={!!deleteTarget} onClose={() => !deleting && setDeleteTarget(null)} title={fmt('research.deleteTitle')}>
        <p className="text-sm text-slate-600">{fmt('research.deleteText')}</p>
        {error && <div className="mt-3 rounded-md bg-red-50 border border-red-200 text-red-700 px-3 py-2 text-sm">{error}</div>}
        <div className="flex justify-end gap-2 pt-4">
          <button className={btnSecondary} onClick={() => setDeleteTarget(null)} disabled={deleting}>
            {fmt('common.cancel')}
          </button>
          <button
            className="inline-flex items-center rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            onClick={confirmDeleteResearch}
            disabled={deleting}
          >
            {deleting ? fmt('settings.testing') : fmt('research.delete')}
          </button>
        </div>
      </Modal>

      {/* Toast */}
      {toast && (
        <div className="fixed bottom-4 right-4 z-50 rounded-lg bg-emerald-600 text-white px-4 py-3 text-sm shadow-lg">
          {toast}
        </div>
      )}
    </div>
  )
}
