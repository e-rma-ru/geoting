import { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import { fmt } from '../i18n.js'
import { btnPrimary, btnSecondary, inputCls, Spinner } from '../components/ui.jsx'

function statusMeta(testStatus, configured) {
  if (testStatus === 'testing') {
    return { label: fmt('settings.testing'), dot: 'bg-blue-500 animate-pulse', tone: 'text-blue-700' }
  }
  switch (testStatus) {
    case 'connected':
      return { label: fmt('settings.connected'), dot: 'bg-emerald-500', tone: 'text-emerald-700' }
    case 'invalid':
      return { label: fmt('settings.invalid'), dot: 'bg-red-500', tone: 'text-red-700' }
    case 'rate_limited':
      return { label: fmt('settings.rateLimited'), dot: 'bg-amber-500', tone: 'text-amber-700' }
    case 'error':
      return { label: fmt('settings.error'), dot: 'bg-red-500', tone: 'text-red-700' }
    default:
      if (configured) return { label: fmt('settings.configured'), dot: 'bg-emerald-500', tone: 'text-emerald-700' }
      return { label: fmt('settings.notConfigured'), dot: 'bg-slate-400', tone: 'text-slate-500' }
  }
}

export default function SettingsPage() {
  const [data, setData] = useState(null)
  const [catalog, setCatalog] = useState({ models: [] })
  const [error, setError] = useState('')
  const [editing, setEditing] = useState(false)
  const [newKey, setNewKey] = useState('')
  const [saving, setSaving] = useState(false)
  const [busy, setBusy] = useState(false)
  const [testState, setTestState] = useState({ status: null, message: '', detail: '' })
  const [defaultModel, setDefaultModel] = useState('')

  async function load() {
    try {
      const s = await api.settings()
      setData(s)
      setDefaultModel(s.routerai.default_model)
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    load()
  }, [])

  useEffect(() => {
    api
      .models()
      .then(setCatalog)
      .catch(() => {})
  }, [])

  const routerai = data?.routerai
  const meta = statusMeta(testState.status, routerai?.configured)

  const sortedModels = useMemo(() => {
    return [...catalog.models].sort((a, b) => a.id.localeCompare(b.id))
  }, [catalog.models])

  async function testConnection() {
    setBusy(true)
    setTestState({ status: 'testing', message: '', detail: '' })
    try {
      const res = await api.testRouterAI()
      setTestState({ status: res.status, message: res.message, detail: res.detail || '' })
    } catch (e) {
      setTestState({ status: 'error', message: e.message, detail: '' })
    } finally {
      setBusy(false)
    }
  }

  async function saveKey() {
    const key = newKey.trim()
    if (!key) return
    setSaving(true)
    setError('')
    try {
      const res = await api.saveRouterAIKey(key)
      setNewKey('')
      setEditing(false)
      setTestState({ status: null, message: '', detail: '' })
      setData((prev) => ({
        ...prev,
        routerai: { ...prev.routerai, configured: true, key_hint: res.key_hint },
      }))
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  async function clearKey() {
    if (!window.confirm(fmt('settings.deleteKeyConfirm'))) return
    setBusy(true)
    setError('')
    try {
      await api.deleteRouterAIKey()
      setEditing(false)
      setNewKey('')
      setTestState({ status: null, message: '', detail: '' })
      setData((prev) => ({
        ...prev,
        routerai: { ...prev.routerai, configured: false, key_hint: '' },
      }))
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function saveDefaultModel(model) {
    setDefaultModel(model)
    try {
      await api.setDefaultModel(model)
    } catch (e) {
      setError(e.message)
    }
  }

  if (!data)
    return error ? <div className="text-red-600 text-sm">{error}</div> : <Spinner label={fmt('settings.loading')} />

  return (
    <div className="max-w-2xl">
      <h1 className="text-2xl font-bold mb-4">{fmt('settings.title')}</h1>
      {error && <div className="mb-4 rounded-md bg-red-50 border border-red-200 text-red-700 px-3 py-2 text-sm">{error}</div>}

      {/* RouterAI gateway */}
      <div className="text-lg font-semibold mb-2">{fmt('settings.routeraiGateway')}</div>
      <div className="bg-white rounded-xl border border-slate-200 p-5 mb-6 flex flex-col gap-4">
        <div className="flex items-start justify-between">
          <div>
            <div className="font-semibold text-lg">RouterAI</div>
            <div className="text-xs text-slate-400 mt-0.5">{fmt('settings.gatewayHint')}</div>
          </div>
          <div className={`flex items-center gap-1.5 text-sm font-medium ${meta.tone}`}>
            <span className={`inline-block w-2.5 h-2.5 rounded-full ${meta.dot}`} />
            {meta.label}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
          <div className="bg-slate-50 rounded-md px-3 py-2">
            <div className="text-xs text-slate-500">{fmt('settings.apiKey')}</div>
            <div className="font-medium mono">{routerai.key_hint ? `[ ${routerai.key_hint} ]` : fmt('settings.keyNotSet')}</div>
          </div>
          <div className="bg-slate-50 rounded-md px-3 py-2">
            <div className="text-xs text-slate-500">{fmt('settings.baseUrl')}</div>
            <div className="font-medium mono break-all">{routerai.base_url}</div>
          </div>
        </div>

        <a href={routerai.docs} target="_blank" rel="noreferrer" className="text-xs text-emerald-700 hover:underline -mt-2">
          {fmt('settings.getKey')} →
        </a>

        {!editing && (
          <div className="flex flex-wrap gap-2">
            <button className={btnSecondary} onClick={testConnection} disabled={busy || !routerai.configured}>
              {fmt('settings.testConnection')}
            </button>
            <button className={btnSecondary} onClick={() => setEditing(true)}>
              {routerai.configured ? fmt('settings.editKey') : fmt('settings.enterKey')}
            </button>
            {routerai.configured && (
              <button className={btnSecondary + ' !text-red-600 !border-red-200 hover:!bg-red-50'} onClick={clearKey} disabled={busy}>
                {fmt('settings.deleteKey')}
              </button>
            )}
          </div>
        )}

        {editing && (
          <div className="space-y-3 border-t border-slate-100 pt-3">
            <div>
              <label className="text-sm font-medium block mb-1">{fmt('settings.apiKey')}</label>
              <input
                type="password"
                autoComplete="new-password"
                className={inputCls}
                placeholder={fmt('settings.newKeyPlaceholder')}
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && saveKey()}
              />
              <p className="text-xs text-slate-400 mt-1">{fmt('settings.keysNote')}</p>
            </div>
            <div className="flex justify-end gap-2">
              <button
                className={btnSecondary}
                onClick={() => {
                  setEditing(false)
                  setNewKey('')
                }}
              >
                {fmt('settings.cancel')}
              </button>
              <button className={btnPrimary} onClick={saveKey} disabled={saving || !newKey.trim()}>
                {saving ? fmt('settings.saving') : fmt('settings.save')}
              </button>
            </div>
          </div>
        )}

        {testState.status === 'testing' && (
          <div className="flex items-center gap-2 text-sm text-blue-700">
            <span className="inline-block w-4 h-4 border-2 border-blue-300 border-t-blue-600 rounded-full animate-spin" />
            {fmt('settings.testing')}
          </div>
        )}

        {testState.status && testState.status !== 'testing' && testState.status !== 'not_configured' && (
          <div
            className={`rounded-md border px-3 py-2 text-sm ${
              testState.status === 'connected'
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : 'bg-red-50 border-red-200 text-red-700'
            }`}
          >
            <div className="font-medium">{testState.message}</div>
            {testState.detail && (
              <details className="mt-1">
                <summary className="text-xs cursor-pointer text-slate-500">{fmt('settings.showDetail')}</summary>
                <pre className="mt-1 text-xs whitespace-pre-wrap text-slate-600 bg-white/60 rounded p-2">{testState.detail}</pre>
              </details>
            )}
          </div>
        )}

        {/* Default model */}
        <div className="border-t border-slate-100 pt-3">
          <label className="text-sm font-medium block mb-1">{fmt('settings.defaultModel')}</label>
          <select
            className={inputCls}
            value={defaultModel}
            onChange={(e) => saveDefaultModel(e.target.value)}
          >
            {sortedModels.map((m) => (
              <option key={m.id} value={m.id}>
                {m.id}
              </option>
            ))}
          </select>
          <p className="text-xs text-slate-400 mt-1">
            {fmt('settings.defaultModelNote')}{' '}
            {catalog.source === 'routerai-live'
              ? `RouterAI · ${catalog.count} ${fmt('settings.models')}`
              : fmt('settings.modelsFallback')}
          </p>
        </div>
      </div>

      <div className="text-lg font-semibold mb-2">{fmt('settings.analyzer')}</div>
      <div className="bg-white rounded-lg border border-slate-200 p-4 mb-6 text-sm">
        <div className="flex gap-8">
          <div><span className="text-slate-500">{fmt('settings.analyzerModel')}:</span> <b className="mono">{data.analyzer.model}</b></div>
        </div>
        <p className="text-xs text-slate-400 mt-2">
          {fmt('settings.analyzerNote')}
        </p>
      </div>

      <div className="text-lg font-semibold mb-2">{fmt('settings.execution')}</div>
      <div className="bg-white rounded-lg border border-slate-200 p-4 text-sm">
        <div className="grid grid-cols-3 gap-4">
          <div><span className="text-slate-500">{fmt('settings.maxConcurrent')}:</span> <b className="mono">{data.concurrency.max_concurrent_requests}</b></div>
          <div><span className="text-slate-500">{fmt('settings.maxRetries')}:</span> <b className="mono">{data.concurrency.max_retries}</b></div>
          <div><span className="text-slate-500">{fmt('settings.timeout')}:</span> <b className="mono">{data.concurrency.timeout_seconds}s</b></div>
        </div>
      </div>
    </div>
  )
}
