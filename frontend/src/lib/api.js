import axios from 'axios'
import { useAuthStore } from '../store/authStore'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 30000,
})

// Interceptor: aggiunge Bearer token
api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Interceptor: gestisce 401 → logout
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default api

// ── API helpers ──────────────────────────────────────────────────────────────

export const authApi = {
  login: (email, password) => {
    const form = new FormData()
    form.append('username', email)
    form.append('password', password)
    return api.post('/api/v1/auth/login', form)
  },
  me: () => api.get('/api/v1/auth/me'),
}

export const periodsApi = {
  list: () => api.get('/api/v1/periods/'),
  create: (data) => api.post('/api/v1/periods/', data),
  get: (id) => api.get(`/api/v1/periods/${id}`),
}

export const activitiesApi = {
  list: (department) => api.get('/api/v1/activities/', { params: { department } }),
  create: (data) => api.post('/api/v1/activities/', data),
  delete: (id) => api.delete(`/api/v1/activities/${id}`),
}

export const servicesApi = {
  list: () => api.get('/api/v1/services/'),
  create: (data) => api.post('/api/v1/services/', data),
}

export const allocationsApi = {
  list: () => api.get('/api/v1/allocations/'),
  create: (data) => api.post('/api/v1/allocations/', data),
  delete: (id) => api.delete(`/api/v1/allocations/${id}`),
}

export const reportsApi = {
  calculate: (periodId) => api.post(`/api/v1/reports/abc/calculate/${periodId}`),
  get: (periodId) => api.get(`/api/v1/reports/abc/${periodId}`),
  kpi: (periodId) => api.get('/api/v1/reports/kpi/summary', { params: { period_id: periodId } }),
  export: (periodId) => `${import.meta.env.VITE_API_URL || ''}/api/v1/reports/export/${periodId}`,
}

export const importsApi = {
  accounting: (formData) => api.post('/api/v1/imports/accounting', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  payroll: (formData) => api.post('/api/v1/imports/payroll', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
  revenues: (formData) => api.post('/api/v1/imports/revenues', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
}

export const simulationApi = {
  run: (periodId, scenario) => api.post(`/api/v1/simulation/combined/${periodId}`, scenario),
  templates: () => api.get('/api/v1/simulation/scenarios/templates'),
}

export const aiApi = {
  driverDiscovery: () => api.get('/api/v1/ai/driver-discovery'),
  forecast: (metric, periods) => api.get('/api/v1/ai/forecast', { params: { metric, periods } }),
  anomalies: () => api.get('/api/v1/ai/anomalies'),
}

export const pmsIntegrationsApi = {
  list: (hotelId) => api.get('/api/v1/pms-integrations/', { params: hotelId ? { hotel_id: hotelId } : {} }),
  get: (id) => api.get(`/api/v1/pms-integrations/${id}`),
  create: (data) => api.post('/api/v1/pms-integrations/', data),
  update: (id, data) => api.put(`/api/v1/pms-integrations/${id}`, data),
  delete: (id) => api.delete(`/api/v1/pms-integrations/${id}`),
  sync: (id) => api.post(`/api/v1/pms-integrations/${id}/sync`),
}
