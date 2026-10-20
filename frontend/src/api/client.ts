import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL ?? ''

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Response interceptor — don't silently swallow errors
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      const msg = error.response.data?.detail ?? error.response.statusText ?? 'API error'
      return Promise.reject(new Error(`[${error.response.status}] ${msg}`))
    }
    if (error.request) {
      return Promise.reject(new Error('Network error: Backend is unreachable. Is the FastAPI server running on port 8000?'))
    }
    return Promise.reject(error)
  }
)
