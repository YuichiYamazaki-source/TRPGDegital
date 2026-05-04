import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? 'http://localhost/api',
  headers: { 'Content-Type': 'application/json' },
})

export const sessions = {
  list: () => api.get('/sessions/'),
  create: (name: string) => api.post('/sessions/', { name }),
  delete: (id: string) => api.delete(`/sessions/${id}`),
}

export const characters = {
  list: (sessionId?: string) =>
    api.get('/characters/', { params: sessionId ? { session_id: sessionId } : {} }),
  get: (id: string) => api.get(`/characters/${id}`),
  create: (payload: { name: string; session_id?: string; data: object }) =>
    api.post('/characters/', payload),
  update: (id: string, payload: object) => api.put(`/characters/${id}`, payload),
}
