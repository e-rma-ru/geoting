import { useLayoutEffect, useRef, useState } from 'react'
import { fmt, t } from '../i18n.js'

export function fmtDate(value) {
  if (!value) return '—'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return String(value)
  return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function fmtNum(value, digits = 1) {
  if (value === null || value === undefined) return '—'
  return Number(value).toLocaleString('ru-RU', { maximumFractionDigits: digits })
}

export function pct(value) {
  if (value === null || value === undefined) return '—'
  return `${fmtNum(value)}%`
}

export function metricLabel(key) {
  return t.metrics[key] || key
}

export function metricHelp(key) {
  return t.metrics_help[key] || ''
}

export function statusLabel(status) {
  return t.statuses[status] || status
}

export function sourceTypeLabel(value) {
  return t.source_types[value] || value
}

export function sentimentLabel(value) {
  return t.sentiments[value] || value
}

export function clusterLabel(value) {
  return t.clusters[value] || value
}

export function intentLabel(value) {
  return t.intents[value] || value
}

export const CLUSTERS = [
  'discovery',
  'children',
  'teenagers',
  'adults',
  'price',
  'comparison',
  'situation',
  'decision',
  'brand',
  'problem',
]

export const PROVIDERS = ['routerai']

export const PROVIDER_LABELS = {
  routerai: 'RouterAI',
  // Legacy labels for historical runs executed through direct providers.
  openai: 'OpenAI (legacy)',
  gemini: 'Google Gemini (legacy)',
  perplexity: 'Perplexity (legacy)',
}

export function statusColor(status) {
  switch (status) {
    case 'completed':
      return 'bg-emerald-100 text-emerald-800'
    case 'running':
      return 'bg-blue-100 text-blue-800'
    case 'queued':
      return 'bg-slate-200 text-slate-700'
    case 'failed':
      return 'bg-red-100 text-red-700'
    case 'draft':
      return 'bg-amber-100 text-amber-800'
    default:
      return 'bg-slate-200 text-slate-700'
  }
}

export function StatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${statusColor(status)}`}>
      {statusLabel(status)}
    </span>
  )
}

export function Spinner({ label }) {
  return (
    <div className="flex items-center gap-2 text-slate-500 text-sm py-4">
      <span className="inline-block w-4 h-4 border-2 border-slate-300 border-t-emerald-500 rounded-full animate-spin" />
      {label || fmt('common.loading')}
    </div>
  )
}

export function EmptyState({ title, hint }) {
  return (
    <div className="text-center py-10 text-slate-400">
      <div className="text-lg font-medium">{title}</div>
      {hint && <div className="text-sm mt-1">{hint}</div>}
    </div>
  )
}

/**
 * Horizontal scroll wrapper for wide tables/grids.
 *
 * The inner container scrolls horizontally (natural table width, columns are
 * never squished). A sticky bottom scrollbar stays available while scrolling
 * the page through a long table and is kept in sync both ways with the real
 * scroll container. It renders only when the content actually overflows.
 */
export function TableScroll({ children, className = '' }) {
  const scrollRef = useRef(null)
  const barRef = useRef(null)
  const spacerRef = useRef(null)
  const [hasOverflow, setHasOverflow] = useState(false)
  const [scrollWidth, setScrollWidth] = useState(0)

  useLayoutEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const update = () => {
      const sw = el.scrollWidth
      setScrollWidth(sw)
      setHasOverflow(sw > el.clientWidth + 1)
      if (spacerRef.current) {
        spacerRef.current.style.width = `${sw}px`
      }
    }
    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    const timer = setTimeout(update, 150)
    return () => {
      ro.disconnect()
      clearTimeout(timer)
    }
  }, [children])

  function onTableScroll() {
    const bar = barRef.current
    const el = scrollRef.current
    if (bar && Math.abs(bar.scrollLeft - el.scrollLeft) > 1) {
      bar.scrollLeft = el.scrollLeft
    }
  }

  function onBarScroll() {
    const bar = barRef.current
    const el = scrollRef.current
    if (el && Math.abs(el.scrollLeft - bar.scrollLeft) > 1) {
      el.scrollLeft = bar.scrollLeft
    }
  }

  return (
    <div className={`relative ${className}`}>
      <div ref={scrollRef} onScroll={onTableScroll} className="table-scroll overflow-x-auto">
        {children}
      </div>
      {hasOverflow && (
        <div
          ref={barRef}
          onScroll={onBarScroll}
          className="sticky bottom-0 z-10 overflow-x-scroll sticky-scrollbar border-t border-slate-200 bg-white/95 backdrop-blur"
          role="scrollbar"
          aria-label={t.common.horizontalScroll || 'horizontal scroll'}
        >
          <div ref={spacerRef} className="h-3" style={scrollWidth ? { width: `${scrollWidth}px` } : undefined} />
        </div>
      )}
    </div>
  )
}

export function MetricCard({ label, value, sub, accent }) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4">
      <div className="text-xs uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-2xl font-bold mono ${accent || 'text-ink'}`}>{value}</div>
      {sub && <div className="text-xs text-slate-400 mt-1">{sub}</div>}
    </div>
  )
}

export function Modal({ open, onClose, title, children }) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200">
          <h3 className="font-semibold text-ink">{title}</h3>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-xl leading-none px-1" aria-label={fmt('common.close')}>
            ×
          </button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  )
}

export const inputCls =
  'w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent'
export const btnPrimary =
  'inline-flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed'
export const btnSecondary =
  'inline-flex items-center gap-1.5 rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50'
export const btnDanger =
  'inline-flex items-center gap-1.5 rounded-md border border-red-200 bg-white px-3 py-2 text-sm font-medium text-red-600 hover:bg-red-50'
