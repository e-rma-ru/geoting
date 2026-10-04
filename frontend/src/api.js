let _on401 = null
export function onAuthFail(cb) {
  _on401 = cb
}

async function request(path, options = {}) {
  const res = await fetch(path, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (res.status === 401 && _on401) {
    _on401()
  }
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
  // auth
  register: (payload) => request('/api/auth/register', { method: 'POST', body: JSON.stringify(payload) }),
  login: (payload) => request('/api/auth/login', { method: 'POST', body: JSON.stringify(payload) }),
  logout: () => request('/api/auth/logout', { method: 'POST' }),
  me: () => request('/api/auth/me'),
  updateProfile: (payload) => request('/api/auth/me', { method: 'PUT', body: JSON.stringify(payload) }),
  changePassword: (payload) => request('/api/auth/change-password', { method: 'POST', body: JSON.stringify(payload) }),

  // organization
  getOrganization: () => request('/api/organization'),
  updateOrganization: (payload) => request('/api/organization', { method: 'PUT', body: JSON.stringify(payload) }),
  listMembers: () => request('/api/organization/members'),
  updateMemberRole: (id, payload) => request(`/api/organization/members/${id}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  deleteMember: (id) => request(`/api/organization/members/${id}`, { method: 'DELETE' }),
  transferOwnership: (payload) => request('/api/organization/transfer-ownership', { method: 'POST', body: JSON.stringify(payload) }),
  createInvite: (payload) => request('/api/organization/invites', { method: 'POST', body: JSON.stringify(payload) }),
  listInvites: () => request('/api/organization/invites'),

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
    const res = await fetch(`/api/projects/${projectId}/prompts/import`, { method: 'POST', body: form, credentials: 'include' })
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