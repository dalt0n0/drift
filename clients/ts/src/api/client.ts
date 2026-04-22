import axios from 'axios'

export const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' },
})

// Attach JWT from storage on every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('drift.token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401, clear token and redirect to login — but not for auth endpoints themselves
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const url: string = err.config?.url ?? ''
    const isAuthEndpoint = url.includes('/auth/login') || url.includes('/auth/refresh')
    if (err.response?.status === 401 && !isAuthEndpoint) {
      localStorage.removeItem('drift.token')
      localStorage.removeItem('drift.user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)
