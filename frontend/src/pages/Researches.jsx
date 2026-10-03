import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { fmt } from '../i18n.js'
import { btnSecondary, EmptyState, fmtDate, Modal, Spinner, StatusBadge, TableScroll } from '../components/ui.jsx'

export default function Researches() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deleteTarget, setDeleteTarget] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [toast, setToast] = useState('')

  useEffect(() => {
    let cancelled = false
    api
      .researches()
      .then((d) => !cancelled && setItems(d))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  async function confirmDelete() {
    if (!deleteTarget) return
    setDeleting(true)
    setError('')
    try {
      await api.deleteResearch(deleteTarget.id)
      setItems((prev) => prev.filter((r) => r.id !== deleteTarget.id))
      setDeleteTarget(null)
      setToast(fmt('research.deleteSuccess'))
      setTimeout(() => setToast(''), 3000)
    } catch (e) {
      setError(`${fmt('research.deleteError')}: ${e.message}`)
    } finally {
      setDeleting(false)
    }
  }

  if (loading) return <Spinner label={fmt('common.loading')} />

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">{fmt('research.title')}</h1>
      {error && <div className="mb-4 rounded-md bg-red-50 border border-red-200 text-red-700 px-3 py-2 text-sm">{error}</div>}
      {items.length === 0 ? (
        <EmptyState title={fmt('research.emptyTitle')} hint={fmt('research.emptyHint')} />
      ) : (
        <div className="bg-white rounded-lg border border-slate-200">
          <TableScroll>
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-2">{fmt('research.research')}</th>
                  <th className="px-4 py-2">{fmt('research.project')}</th>
                  <th className="px-4 py-2">{fmt('research.status')}</th>
                  <th className="px-4 py-2">{fmt('research.size')}</th>
                  <th className="px-4 py-2">{fmt('research.created')}</th>
                  <th className="px-4 py-2 w-24 text-right">{fmt('common.actions')}</th>
                </tr>
              </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id} className="border-t border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-2">
                    <Link to={`/projects/${r.project_id}/research/${r.id}`} className="font-medium text-emerald-700 hover:underline">
                      {r.name}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-slate-500">{fmt('research.project')} #{r.project_id}</td>
                  <td className="px-4 py-2"><StatusBadge status={r.status} /></td>
                  <td className="px-4 py-2 mono">{r.prompts_count}×{r.providers_count}×{r.runs_per_prompt}</td>
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
              ))}
            </tbody>
          </table>
          </TableScroll>
        </div>
      )}

      <Modal open={!!deleteTarget} onClose={() => !deleting && setDeleteTarget(null)} title={fmt('research.deleteTitle')}>
        <p className="text-sm text-slate-600">{fmt('research.deleteText')}</p>
        {error && <div className="mt-3 rounded-md bg-red-50 border border-red-200 text-red-700 px-3 py-2 text-sm">{error}</div>}
        <div className="flex justify-end gap-2 pt-4">
          <button className={btnSecondary} onClick={() => setDeleteTarget(null)} disabled={deleting}>
            {fmt('common.cancel')}
          </button>
          <button
            className="inline-flex items-center rounded-md bg-red-600 px-3 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50"
            onClick={confirmDelete}
            disabled={deleting}
          >
            {deleting ? fmt('settings.testing') : fmt('research.delete')}
          </button>
        </div>
      </Modal>

      {toast && (
        <div className="fixed bottom-4 right-4 z-50 rounded-lg bg-emerald-600 text-white px-4 py-3 text-sm shadow-lg">
          {toast}
        </div>
      )}
    </div>
  )
}
