async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail || JSON.stringify(body)
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  if (res.status === 204) return null
  return res.json()
}

export const api = {
  // projects
  projects: () => request('/api/projects'),
  createProject: (payload) => request('/api/projects', { method: 'POST', body: JSON.stringify(payload) }),
  getProject: (id) => request(`/api/projects/${id}`),
  updateProject: (id, payload) => request(`/api/projects/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deleteProject: (id) => request(`/api/projects/${id}`, { method: 'DELETE' }),

  // prompts
  prompts: (projectId, filters = {}) => {
    const qs = new URLSearchParams()
    if (filters.cluster) qs.set('cluster', filters.cluster)
    if (filters.active !== undefined && filters.active !== null && filters.active !== '') {
      qs.set('active', String(filters.active))
    }
    const query = qs.toString()
    return request(`/api/projects/${projectId}/prompts${query ? `?${query}` : ''}`)
  },
  createPrompt: (projectId, payload) =>
    request(`/api/projects/${projectId}/prompts`, { method: 'POST', body: JSON.stringify(payload) }),
  updatePrompt: (id, payload) => request(`/api/prompts/${id}`, { method: 'PUT', body: JSON.stringify(payload) }),
  deletePrompt: (id) => request(`/api/prompts/${id}`, { method: 'DELETE' }),
  importPromptsCsv: async (projectId, file) => {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch(`/api/projects/${projectId}/prompts/import`, { method: 'POST', body: form })
    if (!res.ok) {
      let detail = res.statusText
      try {
        detail = (await res.json()).detail
      } catch {
        /* ignore */
      }
      throw new Error(detail)
    }
    return res.json()
  },
  exportPromptsCsvUrl: (projectId) => `/api/projects/${projectId}/prompts/export`,

  // research
  researches: (projectId) => request(`/api/projects/${projectId}/research`),
  createResearch: (payload) => request('/api/research', { method: 'POST', body: JSON.stringify(payload) }),  getResearch: (id) => request(`/api/research/${id}`),
  deleteResearch: (id) => request(`/api/research/${id}`, { method: 'DELETE' }),
  researchRuns: (id) => request(`/api/research/${id}/runs`),
  runDetail: (runId) => request(`/api/runs/${runId}`),
  dashboard: (researchId) => request(`/api/research/${researchId}/dashboard`),
  researchMetrics: (researchId) => request(`/api/research/${researchId}/metrics`),
  projectDashboard: (projectId) => request(`/api/projects/${projectId}/dashboard`),
  compare: (researchIds) => request(`/api/compare?research_ids=${researchIds.join(',')}`),
  researchProfiles: (researchId) => request(`/api/research/${researchId}/profiles`),
  buildProfiles: (researchId) => request(`/api/research/${researchId}/profiles/build`, { method: 'POST' }),

  // settings
  settings: () => request('/api/settings'),
  saveRouterAIKey: (apiKey) =>
    request('/api/settings/routerai/key', { method: 'POST', body: JSON.stringify({ api_key: apiKey }) }),
  deleteRouterAIKey: () => request('/api/settings/routerai/key', { method: 'DELETE' }),
  testRouterAI: () => request('/api/settings/routerai/test', { method: 'POST' }),
  setDefaultModel: (model) => request('/api/settings/model', { method: 'POST', body: JSON.stringify({ model }) }),
  models: () => request('/api/settings/models'),
}
