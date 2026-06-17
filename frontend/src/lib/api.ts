import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('nexa-auth')
      window.location.href = '/'
    }
    return Promise.reject(err)
  }
)

export default api
