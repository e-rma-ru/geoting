import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { api } from '../api.js'
import { fmt, t } from '../i18n.js'
import {
  btnPrimary, btnSecondary, EmptyState, fmtDate, fmtNum, metricLabel, MetricCard, Modal, pct,
  PROVIDER_LABELS, Spinner, statusLabel, StatusBadge, TableScroll,
} from '../components/ui.jsx'

function TrendChart({ data, dataKey, name, color }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="text-sm font-semibold mb-2">{name}</div>
      <ResponsiveContainer width="100%" height={140}>
        <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} domain={[0, (dataMax) => Math.max(100, Math.ceil(dataMax))]} allowDecimals />
          <Tooltip />
          <Line type="monotone" dataKey={dataKey} name={name} stroke={color} strokeWidth={2} dot={{ r: 3 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export default function ResearchDashboard() {
  const { researchId, projectId: projectIdParam } = useParams()
  const [searchParams] = useSearchParams()
  const [detail, setDetail] = useState(null)
  const [timeseries, setTimeseries] = useState([])
  const [compareData, setCompareData] = useState(null)
  const [sourceFilter, setSourceFilter] = useState('all')
  const [onlyMentioned, setOnlyMentioned] = useState(false)
  const [modelFilter, setModelFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const projectId = projectIdParam || detail?.research?.project_id

  const compareIds = useMemo(() => {
    const ids = searchParams.get('compare')
    if (!ids) return []
    return [String(researchId), ...ids.split(',').filter(Boolean)]
  }, [searchParams, researchId])

  const load = useCallback(async () => {
    try {
      setError('')
      const d = await api.dashboard(researchId)
      setDetail(d)
      if (compareIds.length >= 2) {
        const c = await api.compare(compareIds)
        setCompareData(c)
      } else {
        setCompareData(null)
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [researchId, compareIds.join(',')])

  useEffect(() => {
    load()
  }, [load])

  // Auto-refresh while research is running
  const isActive = detail && (detail.research.status === 'running' || detail.research.status === 'queued')
  useEffect(() => {
    if (!isActive) return
    const t = setInterval(() => load(), 4000)
    return () => clearInterval(t)
  }, [isActive, load])

  // charts data
  const chartData = useMemo(() => {
    if (!projectId) return []
    return timeseries.map((t) => ({
      label: fmtDate(t.created_at).split(',')[0],
      mention: t.metrics.mention_rate,
      top3: t.metrics.top3_rate,
      recommendation: t.metrics.recommendation_rate,
      citation: t.metrics.citation_rate,
      accuracy: t.metrics.entity_accuracy,
    }))
  }, [timeseries, projectId])

  useEffect(() => {
    let cancelled = false
    if (!projectId) return
    api.projectDashboard(projectId)
      .then((pd) => {
        if (!cancelled) setTimeseries(pd.timeseries)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [projectId])

  const filteredSources = useMemo(() => {
    const sources = detail?.sources || []
    switch (sourceFilter) {
      case 'brand':
        return sources.filter((s) => s.supports_brand > 0)
      case 'competitor':
        return sources.filter((s) => s.supports_brand === 0)
      default:
        return sources
    }
  }, [detail?.sources, sourceFilter])

  const promptResults = useMemo(() => {
    const all = detail?.prompt_results || []
    const byModel = modelFilter ? all.filter((r) => r.model === modelFilter) : all
    if (!onlyMentioned) return byModel
    return byModel.filter((r) => r.brand_mentioned === true)
  }, [detail?.prompt_results, onlyMentioned, modelFilter])

  if (loading) return <Spinner label={fmt('dashboard.loading')} />
  if (!detail)
    return (
      <div className="text-center py-10 text-slate-400">
        <div className="text-lg font-medium">{fmt('dashboard.unavailable')}</div>
        {error && <div className="text-sm mt-1">{error}</div>}
        <Link to="/researches" className="inline-block mt-3 text-sm text-emerald-700 hover:underline">
          {fmt('dashboard.profilesGoBack')}
        </Link>
      </div>
    )

  const m = detail.metrics

  return (
    <div>
      {error && <div className="mb-4 rounded-md bg-red-50 border border-red-200 text-red-700 px-3 py-2 text-sm">{error}</div>}

      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-500">
            {detail.research.status === 'running' || detail.research.status === 'queued' ? fmt('research.title') : fmt('dashboard.visibility')}
          </div>
          <h1 className="text-2xl font-bold">{detail.research.name}</h1>
          <div className="text-sm text-slate-500">
            {fmtDate(detail.research.created_at)} · {fmt('research.dimensions', { prompts: detail.research.prompts_count, providers: detail.research.models?.length ?? detail.research.providers_count, runs: detail.research.runs_per_prompt })}
            {' '}· <StatusBadge status={detail.research.status} />
          </div>
          {(detail.research.models || []).length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-1.5">
              {detail.research.models.map((model) => (
                <span key={model} className="text-xs bg-white border border-slate-200 rounded-full px-2 py-0.5 text-slate-600 mono">{model}</span>
              ))}
            </div>
          )}
        </div>
        <Link to={`/projects/${projectId}`} className={btnSecondary}>← {fmt('projects.title')}</Link>
      </div>

      {(detail.research.status === 'running' || detail.research.status === 'queued') && (
        <div className="mb-4 rounded-lg bg-blue-50 border border-blue-200 text-blue-800 px-4 py-3 text-sm">
          {fmt('research.runningPartial', { completed: m.completed_runs, total: m.total_runs })}
        </div>
      )}

      {/* GEO VISIBILITY metrics */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mb-2">
        <MetricCard label={metricLabel('mention_rate')} value={pct(m.mention_rate)} sub={`${m.analyzed_runs} ${fmt('dashboard.analyzedRuns')}`} />
        <MetricCard label={metricLabel('top3_rate')} value={pct(m.top3_rate)} />
        <MetricCard label={metricLabel('average_position')} value={fmtNum(m.average_position)} />
        <MetricCard label={metricLabel('recommendation_rate')} value={pct(m.recommendation_rate)} sub={fmtNum(m.average_recommendation_score) + ' ' + fmt('dashboard.avgScore')} />
        <MetricCard label={metricLabel('citation_rate')} value={pct(m.citation_rate)} />
        <MetricCard label={metricLabel('entity_accuracy')} value={fmtNum(m.entity_accuracy, 0)} />
      </div>
      <div className="mb-6 flex items-center gap-3 text-xs text-slate-500">
        <span>{fmt('dashboard.sov')}: <b className="text-ink">{pct(m.share_of_voice)}</b> {fmt('dashboard.sovNote')}</span>
        <span>· {fmt('dashboard.runsFailures', { failed: m.failed_runs, total: m.total_runs })}</span>
        <span className="text-slate-400">{fmt('dashboard.heuristicNote')}</span>
      </div>

      {/* Comparison panel */}
      {compareData && (
        <div className="bg-white rounded-xl border border-slate-200 mb-6">
          <div className="px-4 py-3 border-b border-slate-200 bg-slate-50 font-semibold text-sm">
            {fmt('dashboard.comparison')}
          </div>
          <TableScroll>
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">{fmt('dashboard.metric')}</th>
                  {compareData.points.map((p) => (
                    <th key={p.research_id} className="px-4 py-2">{fmtDate(p.created_at).split(',')[0]}</th>
                  ))}
                  <th className="px-4 py-2">{fmt('dashboard.change')}</th>
                </tr>
              </thead>
              <tbody>
                {compareData.comparison.map((row) => (
                  <tr key={row.metric} className="border-t border-slate-100">
                    <td className="px-4 py-2 font-medium">{metricLabel(row.metric)}</td>
                    {row.values.map((v, idx) => (
                      <td key={idx} className="px-4 py-2 mono">
                        {row.metric.includes('rate') || row.metric === 'entity_accuracy' || row.metric === 'share_of_voice'
                          ? pct(v)
                          : fmtNum(v)}
                      </td>
                    ))}
                    <td className="px-4 py-2 mono">
                      {row.diff === null || row.diff === undefined ? (
                        <span className="text-slate-400">—</span>
                      ) : (
                        <span className={row.diff > 0 ? 'text-emerald-700' : row.diff < 0 ? 'text-red-600' : 'text-slate-500'}>
                          {row.diff > 0 ? '+' : ''}{fmtNum(row.diff)}
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableScroll>
        </div>
      )}

      {/* Trends */}
      {chartData.length >= 1 && (
        <>
          <div className="text-lg font-semibold mt-6 mb-2">{fmt('dashboard.dynamics')}</div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
            <TrendChart data={chartData} dataKey="mention" name={metricLabel('mention_rate')} color="#10b981" />
            <TrendChart data={chartData} dataKey="top3" name={metricLabel('top3_rate')} color="#3b82f6" />
            <TrendChart data={chartData} dataKey="recommendation" name={metricLabel('recommendation_rate')} color="#8b5cf6" />
            <TrendChart data={chartData} dataKey="citation" name={metricLabel('citation_rate')} color="#f59e0b" />
            <TrendChart data={chartData} dataKey="accuracy" name={metricLabel('entity_accuracy')} color="#ef4444" />
          </div>
        </>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Prompt results */}
        <div className="lg:col-span-2 min-w-0">
          <div className="flex items-center justify-between mb-2 flex-wrap gap-2">
            <div className="text-lg font-semibold">{fmt('dashboard.resultsByPrompt')}</div>
            <div className="flex items-center gap-3 flex-wrap">
              <label className="flex items-center gap-2 text-sm text-slate-700 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={onlyMentioned}
                  onChange={(e) => setOnlyMentioned(e.target.checked)}
                  className="w-4 h-4 accent-emerald-600"
                />
                {fmt('dashboard.onlyMentioned')}
              </label>
              {(detail.research.models || []).length > 0 && (
                <select
                  className="text-sm border border-slate-300 rounded-md px-2 py-1"
                  value={modelFilter}
                  onChange={(e) => setModelFilter(e.target.value)}
                >
                  <option value="">{fmt('dashboard.allModels')}</option>
                  {detail.research.models.map((model) => (
                    <option key={model} value={model}>{model}</option>
                  ))}
                </select>
              )}
              <span className="text-xs text-slate-500 mono">
                {promptResults.length} {fmt('dashboard.of')} {modelFilter ? detail.prompt_results.filter((r) => r.model === modelFilter).length : detail.prompt_results.length}
              </span>
            </div>
          </div>
          <div className="bg-white rounded-lg border border-slate-200">
            <TableScroll>
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-3 py-2">{fmt('dashboard.prompt')}</th>
                    <th className="px-3 py-2">{fmt('dashboard.cluster')}</th>
                    <th className="px-3 py-2">{fmt('dashboard.provider')}</th>
                    <th className="px-3 py-2 text-right">{fmt('dashboard.mention')}</th>
                    <th className="px-3 py-2 text-right">{fmt('dashboard.position')}</th>
                    <th className="px-3 py-2 text-right">{fmt('dashboard.recommendation')}</th>
                    <th className="px-3 py-2 text-right">{fmt('dashboard.accuracy')}</th>
                  </tr>
                </thead>
              <tbody>
                {promptResults.length === 0 && (
                  <tr>
                    <td colSpan={7} className="px-3 py-6 text-center text-slate-400 text-sm">
                      {onlyMentioned ? fmt('dashboard.noMentionedResults') : fmt('dashboard.noResults')}
                    </td>
                  </tr>
                )}
                {promptResults.map((r) => {
                  const mentioned = r.brand_mentioned === true
                  return (
                    <tr
                      key={r.run_id}
                      className={`border-t border-slate-100 cursor-pointer ${
                        mentioned ? 'bg-emerald-50/70 hover:bg-emerald-100/60' : 'hover:bg-slate-50'
                      }`}
                      onClick={() => (window.location.href = `/runs/${r.run_id}`)}
                    >
                      <td className="px-3 py-2 max-w-[260px]">
                      <div className="truncate" title={r.prompt_text}>{r.prompt_text}</div>
                      <div className="text-[11px] text-slate-400">
                        #{r.run_number} {r.model ? `· ${r.model.split('/').pop()}` : ''} · {statusLabel(r.run_status)}
                      </div>
                      </td>
                      <td className="px-3 py-2 text-slate-500">{r.cluster || '—'}</td>
                      <td className="px-3 py-2">{PROVIDER_LABELS[r.provider] || r.provider}</td>
                      <td className="px-3 py-2 text-right">{r.brand_mentioned === null ? '—' : r.brand_mentioned ? '✓' : '—'}</td>
                      <td className="px-3 py-2 text-right mono">{fmtNum(r.brand_position)}</td>
                      <td className="px-3 py-2 text-right mono">{r.recommendation_score ?? '—'}</td>
                      <td className="px-3 py-2 text-right mono">{r.accuracy_score ?? '—'}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            </TableScroll>
          </div>
        </div>

        {/* Sources + competitors */}
        <div className="space-y-6 min-w-0">
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="text-lg font-semibold">{fmt('dashboard.mostCited')}</div>
              <select
                className="text-sm border border-slate-300 rounded-md px-2 py-1"
                value={sourceFilter}
                onChange={(e) => setSourceFilter(e.target.value)}
              >
                <option value="all">{fmt('dashboard.filterAll')}</option>
                <option value="brand">{fmt('dashboard.filterBrand')}</option>
                <option value="competitor">{fmt('dashboard.filterCompetitor')}</option>
              </select>
            </div>
            <div className="bg-white rounded-lg border border-slate-200">
              <TableScroll>
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                    <tr><th className="px-3 py-2">{fmt('dashboard.sources')}</th><th className="px-3 py-2 text-right">{fmt('dashboard.citations')}</th></tr>
                  </thead>
                  <tbody>
                    {filteredSources.length === 0 && (
                      <tr><td colSpan={2} className="px-3 py-4 text-center text-slate-400 text-sm">{fmt('dashboard.noSources')}</td></tr>
                    )}
                    {filteredSources.map((s) => (
                      <tr key={s.domain} className="border-t border-slate-100">
                        <td className="px-3 py-1.5 mono text-xs">{s.domain}</td>
                        <td className="px-3 py-1.5 text-right mono">
                          {s.count}
                          {s.supports_brand > 0 && <span className="text-emerald-600 ml-1">·{s.supports_brand} {fmt('dashboard.brandCount')}</span>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableScroll>
            </div>
          </div>

          <div>
            <div className="text-lg font-semibold mb-2">{fmt('dashboard.competitors')}</div>
            <div className="bg-white rounded-lg border border-slate-200">
              <TableScroll>
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2">{fmt('dashboard.brand')}</th>
                      <th className="px-3 py-2 text-right">{fmt('dashboard.mentions')}</th>
                      <th className="px-3 py-2 text-right">{fmt('metrics.top3_rate')}</th>
                      <th className="px-3 py-2 text-right">{fmt('metrics.average_position')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.competitors.length === 0 && (
                      <tr><td colSpan={4} className="px-3 py-4 text-center text-slate-400 text-sm">{fmt('dashboard.noCompetitors')}</td></tr>
                    )}
                    {detail.competitors.map((c) => (
                      <tr key={c.name} className="border-t border-slate-100">
                        <td className="px-3 py-1.5">{c.name}</td>
                        <td className="px-3 py-1.5 text-right mono">{c.mentions}</td>
                        <td className="px-3 py-1.5 text-right mono">{c.top3}</td>
                        <td className="px-3 py-1.5 text-right mono">{fmtNum(c.avg_position)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableScroll>
            </div>
            <p className="text-[11px] text-slate-400 mt-1">{fmt('dashboard.competitorsNote')}</p>
          </div>
        </div>
      </div>

      {/* AI Profiles */}
      <ProfilesSection researchId={researchId} />
    </div>
  )
}

const PROFILE_CATEGORY_LABELS = {
  characteristic: t.dashboard.profilesCharacteristics,
  advantage: t.dashboard.profilesAdvantages,
  program: t.dashboard.profilesPrograms,
  audience: t.dashboard.profilesAudience,
  positioning: t.dashboard.profilesPositioning,
}

function FactRow({ fact, companyMentions }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-slate-100 rounded-md">
      <button
        className="w-full text-left px-3 py-1.5 text-sm flex items-center justify-between gap-2 hover:bg-slate-50"
        onClick={() => setOpen((v) => !v)}
        title={fmt('dashboard.profilesDrilldownRuns')}
      >
        <span className="font-medium">{fact.normalized_label}</span>
        <span className="mono text-slate-500 whitespace-nowrap">
          {fact.frequency}/{companyMentions} ({fact.frequency_percent}%)
        </span>
      </button>
      {open && (
        <div className="px-3 pb-2 text-xs text-slate-500 border-t border-slate-100 pt-1.5">
          <div>{fmt('dashboard.profilesDrilldownRuns')}:</div>
          <div className="flex flex-wrap gap-1 mt-1">
            {fact.run_ids.map((id) => (
              <a
                key={id}
                href={`/runs/${id}`}
                className="inline-block bg-slate-100 border border-slate-200 rounded px-1.5 py-0.5 hover:bg-emerald-50 hover:text-emerald-800 mono"
              >
                run #{id}
              </a>
            ))}
          </div>
          {fact.raw_mentions.length > 0 && (
            <details className="mt-1.5">
              <summary className="cursor-pointer">{fmt('dashboard.profilesRawFormulations')}</summary>
              <ul className="list-disc ml-4 mt-1 space-y-0.5">
                {fact.raw_mentions.map((r, i) => (
                  <li key={i}>«{r}»</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  )
}

function CompanyCard({ profile }) {
  const [showRawDesc, setShowRawDesc] = useState(false)
  const groups = useMemo(() => {
    const g = {}
    for (const f of profile.facts) {
      if (!g[f.category]) g[f.category] = []
      g[f.category].push(f)
    }
    return g
  }, [profile.facts])

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="flex items-start justify-between gap-2">
        <div className="font-semibold text-lg">{profile.company_name}</div>
        <div className="text-sm text-slate-500 mono whitespace-nowrap">
          {profile.mention_count} {fmt('dashboard.profilesMentions')} · {fmt('dashboard.profilesTop3')}: {profile.top3_count}
        </div>
      </div>
      {profile.is_heuristic && <div className="text-xs text-amber-600 mt-1">{fmt('dashboard.profilesHeuristicNote')}</div>}

      <div className="mt-3">
        <div className="text-xs uppercase tracking-wide text-slate-400">{fmt('dashboard.profilesDescriptionLabel')}</div>
        <p className="text-sm text-slate-700 mt-1">{profile.description || fmt('dashboard.profilesDescriptionFallback')}</p>
        {profile.description_raw.length > 1 && (
          <button className="text-xs text-slate-500 hover:text-ink mt-1" onClick={() => setShowRawDesc((v) => !v)}>
            {showRawDesc ? fmt('dashboard.profilesHideRawDescriptions') : fmt('dashboard.profilesRawDescriptions')}
          </button>
        )}
        {showRawDesc && (
          <ul className="text-xs text-slate-500 list-disc ml-4 mt-1 space-y-0.5">
            {profile.description_raw.map((d, i) => (
              <li key={i}>{d}</li>
            ))}
          </ul>
        )}
      </div>

      {Object.entries(groups).map(([cat, facts]) => (
        <div key={cat} className="mt-3">
          <div className="text-xs uppercase tracking-wide text-slate-400 mb-1">{PROFILE_CATEGORY_LABELS[cat] || cat}</div>
          <div className="space-y-1">
            {facts.map((f) => (
              <FactRow key={f.category + '|' + f.normalized_label} fact={f} companyMentions={profile.mention_count} />
            ))}
          </div>
        </div>
      ))}

      {profile.summary_text && (
        <div className="mt-3 bg-slate-50 rounded-md p-3">
          <div className="text-xs uppercase tracking-wide text-slate-400 mb-1">{fmt('dashboard.profilesSummaryLabel')}</div>
          <p className="text-sm text-slate-600">{profile.summary_text}</p>
        </div>
      )}
    </div>
  )
}

function ComparisonTable({ profiles }) {
  const rows = useMemo(() => {
    const map = new Map()
    for (const p of profiles) {
      for (const f of p.facts) {
        const key = f.category + '|' + f.normalized_label
        if (!map.has(key)) map.set(key, { category: f.category, label: f.normalized_label })
      }
    }
    const all = [...map.values()]
    return all
      .map((r) => ({
        ...r,
        total: profiles.reduce((s, p) => {
          const f = p.facts.find((x) => x.category === r.category && x.normalized_label === r.label)
          return s + (f ? f.frequency : 0)
        }, 0),
      }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 20)
  }, [profiles])

  if (rows.length === 0) return null
  return (
    <div className="bg-white rounded-xl border border-slate-200">
      <TableScroll>
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
            <tr>
              <th className="px-3 py-2">{fmt('dashboard.characteristic')}</th>
              {profiles.map((p) => (
                <th key={p.company_name} className="px-3 py-2 text-right">{p.company_name}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.category + '|' + r.label} className="border-t border-slate-100">
                <td className="px-3 py-1.5 font-medium">
                  {r.category === 'characteristic' ? r.label : `${PROFILE_CATEGORY_LABELS[r.category] || r.category}: ${r.label}`}
                </td>
                {profiles.map((p) => {
                  const f = p.facts.find((x) => x.category === r.category && x.normalized_label === r.label)
                  return (
                    <td key={p.company_name} className="px-3 py-1.5 text-right mono">
                      {f ? `${f.frequency}/${p.mention_count}` : fmt('dashboard.profilesEmptyCell')}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </TableScroll>
    </div>
  )
}

function Observations({ profiles }) {
  const lines = profiles.map((p) => {
    const top = p.facts[0]
    return top
      ? fmt('dashboard.profilesObservationLine', {
          company: p.company_name,
          label: top.normalized_label,
          freq: top.frequency,
          mentions: p.mention_count,
        })
      : fmt('dashboard.profilesObservationNoFacts', { company: p.company_name })
  })
  return (
    <div className="mt-8 space-y-3">
      <div className="bg-white rounded-xl border border-slate-200 p-4">
        <div className="text-sm font-semibold mb-2">{fmt('dashboard.profilesObservations')}</div>
        <ul className="text-sm text-slate-600 list-disc ml-5 space-y-1">
          {lines.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
      </div>
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4">
        <div className="text-sm font-semibold mb-1">{fmt('dashboard.profilesHypotheses')}</div>
        <p className="text-sm text-amber-800">{fmt('dashboard.profilesHypothesisNote')}</p>
      </div>
    </div>
  )
}

function ProfilesSection({ researchId }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [building, setBuilding] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [notice, setNotice] = useState('')

  const load = useCallback(async () => {
    try {
      const d = await api.researchProfiles(researchId)
      setData(d)
    } catch {
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [researchId])

  useEffect(() => {
    setLoading(true)
    load()
  }, [load])

  async function build() {
    setBuilding(true)
    setNotice('')
    setShowConfirm(false)
    try {
      const d = await api.buildProfiles(researchId)
      setData(d)
      setNotice(fmt('dashboard.profilesBuildDone'))
      setTimeout(() => setNotice(''), 4000)
    } catch (e) {
      setNotice(`${fmt('dashboard.profilesBuildError')}: ${e.message}`)
    } finally {
      setBuilding(false)
    }
  }

  return (
    <div className="mt-8">
      <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
        <div className="text-xl font-bold">{fmt('dashboard.profiles')}</div>
        <button className={btnSecondary} onClick={() => setShowConfirm(true)} disabled={building}>
          {building ? fmt('dashboard.profilesBuilding') : fmt('dashboard.profilesBuild')}
        </button>
      </div>
      {notice && <div className="mb-3 rounded-md bg-emerald-50 border border-emerald-200 text-emerald-800 px-3 py-2 text-sm">{notice}</div>}
      {building && <Spinner label={fmt('dashboard.profilesBuilding')} />}
      {!building && loading && <Spinner label={fmt('common.loading')} />}
      {!building && !loading && data && !data.built && (
        <EmptyState title={fmt('dashboard.profilesNotBuilt')} hint={fmt('dashboard.profilesNotBuiltHint')} />
      )}
      {!building && !loading && data && data.built && data.profiles.length === 0 && (
        <EmptyState title={fmt('dashboard.profilesNoData')} hint={fmt('dashboard.profilesNoMentions')} />
      )}
      {!building && !loading && data && data.built && data.profiles.length > 0 && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {data.profiles.map((p) => (
              <CompanyCard key={p.company_name} profile={p} />
            ))}
          </div>
          <div className="mt-8">
            <div className="text-lg font-semibold mb-2">{fmt('dashboard.profilesComparison')}</div>
            <ComparisonTable profiles={data.profiles} />
          </div>
          <Observations profiles={data.profiles} />
        </>
      )}

      <Modal open={showConfirm} onClose={() => setShowConfirm(false)} title={fmt('dashboard.profilesBuildConfirmTitle')}>
        <p className="text-sm text-slate-600">{fmt('dashboard.profilesBuildConfirmText')}</p>
        <div className="flex justify-end gap-2 pt-4">
          <button className={btnSecondary} onClick={() => setShowConfirm(false)}>{fmt('common.cancel')}</button>
          <button className={btnPrimary} onClick={build}>{fmt('research.run')}</button>
        </div>
      </Modal>
    </div>
  )
}
