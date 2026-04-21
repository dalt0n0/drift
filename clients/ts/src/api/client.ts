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

// On 401, clear token and redirect to login
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('drift.token')
      localStorage.removeItem('drift.user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)
