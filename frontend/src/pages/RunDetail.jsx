import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api.js'
import { fmt } from '../i18n.js'
import {
  EmptyState, fmtNum, intentLabel, MetricCard, PROVIDER_LABELS, sentimentLabel, sourceTypeLabel, Spinner, StatusBadge,
} from '../components/ui.jsx'

export default function RunDetail() {
  const { runId } = useParams()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [showRaw, setShowRaw] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api
      .runDetail(runId)
      .then((d) => {
        if (!cancelled) {
          setData(d)
          setError('')
        }
      })
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [runId])

  if (loading) return <Spinner label={fmt('run.loading')} />
  if (!data) return <EmptyState title={fmt('run.notFound')} hint={error} />

  const { run, prompt, analysis, citations, competitors } = data

  return (
    <div>
      <div className="mb-4">
        <Link to={`/research/${run.research_id}`} className="text-sm text-emerald-700 hover:underline">{fmt('run.backToDashboard')}</Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4 min-w-0">
          {/* Prompt */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="text-xs uppercase tracking-wide text-slate-500 mb-1">{fmt('run.prompt')}</div>
            <p className="text-lg font-medium">{prompt?.text}</p>
            <div className="flex gap-2 mt-2">
              <span className="text-xs bg-slate-100 border border-slate-200 rounded-full px-2 py-0.5">{prompt?.cluster || '—'}</span>
              <span className="text-xs bg-slate-100 border border-slate-200 rounded-full px-2 py-0.5">{fmt('run.intent')}: {intentLabel(prompt?.intent) || '—'}</span>
            </div>
          </div>

          {/* Provider */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="text-xs uppercase tracking-wide text-slate-500 mb-1">{fmt('run.provider')}</div>
            <div className="flex items-center gap-3">
              <span className="font-semibold">{PROVIDER_LABELS[run.provider] || run.provider}</span>
              <span className="text-sm text-slate-500 mono">{run.model}</span>
              <StatusBadge status={run.status} />
              <span className="text-xs text-slate-400">{run.response_time_ms ? `${fmtNum(run.response_time_ms, 0)} ${fmt('run.ms')}` : ''}</span>
            </div>
            {run.error_message && (
              <div className="mt-3 rounded-md bg-red-50 border border-red-200 text-red-700 px-3 py-2 text-sm">{run.error_message}</div>
            )}
          </div>

          {/* Raw answer */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs uppercase tracking-wide text-slate-500">{fmt('run.rawAnswer')}</div>
              <button className="text-sm text-slate-500 hover:text-ink" onClick={() => setShowRaw((v) => !v)}>
                {showRaw ? fmt('run.hideRaw') : fmt('run.showRaw')}
              </button>
            </div>
            {showRaw && run.raw_response ? (
              <pre className="bg-slate-50 border border-slate-200 rounded-md p-3 text-xs overflow-x-auto max-h-80">
                {JSON.stringify(run.raw_response, null, 2)}
              </pre>
            ) : (
              <p className="whitespace-pre-wrap text-sm leading-relaxed">{run.response_text || '—'}</p>
            )}
          </div>
        </div>

        <div className="space-y-4 min-w-0">
          {/* Analysis */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="text-xs uppercase tracking-wide text-slate-500 mb-2">
              {analysis?.is_heuristic ? fmt('run.analysisHeuristic') : fmt('run.analysisAI')}
            </div>
            {!analysis ? (
              <p className="text-sm text-slate-400">{fmt('run.analysisUnavailable')}</p>
            ) : (
              <div>
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <MetricCard label={fmt('run.mention')} value={analysis.brand_mentioned ? 'Да' : 'Нет'} />
                  <MetricCard label={fmt('run.position')} value={analysis.brand_position ?? '—'} />
                  <MetricCard label={fmt('run.recommendationScore')} value={analysis.recommendation_score ?? '—'} sub="0–5" />
                  <MetricCard label={fmt('run.accuracy')} value={analysis.accuracy_score ?? '—'} sub="0–100" />
                </div>
                <div className="grid grid-cols-2 gap-3 text-sm mb-3">
                  <div className="bg-slate-50 rounded-md p-2">
                    <div className="text-xs text-slate-500">{fmt('run.sentiment')}</div>
                    <div className="font-medium">{analysis.sentiment ? sentimentLabel(analysis.sentiment) : '—'}</div>
                  </div>
                  <div className="bg-slate-50 rounded-md p-2">
                    <div className="text-xs text-slate-500">{fmt('run.confidence')}</div>
                    <div className="font-medium mono">{analysis.confidence ?? '—'}</div>
                  </div>
                </div>
                {analysis.reasoning && (
                  <div className="bg-slate-50 rounded-md p-2">
                    <div className="text-xs text-slate-500 mb-1">{fmt('run.reasoning')}</div>
                    <p className="text-sm text-slate-600">{analysis.reasoning}</p>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Sources */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="text-xs uppercase tracking-wide text-slate-500 mb-2">{fmt('run.sources')} ({citations.length})</div>
            {citations.length === 0 ? (
              <p className="text-sm text-slate-400">{fmt('run.sourcesEmpty')}</p>
            ) : (
              <ul className="space-y-2">
                {citations.map((c) => (
                  <li key={c.id} className="text-sm border border-slate-100 rounded-md p-2">
                    <a className="text-emerald-700 hover:underline font-medium break-all" href={c.url} target="_blank" rel="noreferrer">
                      {c.title || c.url}
                    </a>
                    <div className="text-xs text-slate-400 mono mt-0.5">
                      {c.domain} · {sourceTypeLabel(c.source_type)}
                      {c.supports_brand ? <span className="text-emerald-600 font-medium"> · {fmt('run.supportsBrand')}</span> : null}
                    </div>
                    {c.cited_text && <div className="text-xs text-slate-500 mt-1">«{c.cited_text.slice(0, 200)}»</div>}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Competitors */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="text-xs uppercase tracking-wide text-slate-500 mb-2">{fmt('run.competitors')} ({competitors.length})</div>
            {competitors.length === 0 ? (
              <p className="text-sm text-slate-400">{fmt('run.competitorsEmpty')}</p>
            ) : (
              <table className="w-full text-sm">
                <tbody>
                  {competitors.map((c) => (
                    <tr key={c.id} className="border-t border-slate-100 first:border-0">
                      <td className="py-1.5 font-medium">{c.name}</td>
                      <td className="py-1.5 text-right mono">{fmt('run.pos')} {c.position ?? '—'}</td>
                      <td className="py-1.5 text-right mono">{fmt('run.rec')} {c.recommendation_score ?? '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
