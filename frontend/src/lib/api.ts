import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// توکن را در هر درخواست مستقیم از localStorage می‌خوانیم تا هنگام باز شدن مجدد اپ
// (موبایل/PWA) رِیس بین rehydrate و اولین درخواست رخ ندهد و کاربر لاگ‌اوت نشود.
function readToken(): string | null {
  try {
    const raw = localStorage.getItem('nexa-auth')
    if (!raw) return null
    return JSON.parse(raw)?.state?.token || null
  } catch {
    return null
  }
}

api.interceptors.request.use((config) => {
  const token = readToken()
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    // فقط وقتی واقعاً توکن داشتیم و سرور ردش کرد لاگ‌اوت کن (نه روی خطای گذرا/شبکه)
    if (err.response?.status === 401 && readToken()) {
      localStorage.removeItem('nexa-auth')
      if (window.location.pathname !== '/') window.location.href = '/'
    }
    return Promise.reject(err)
  }
)

export default api
