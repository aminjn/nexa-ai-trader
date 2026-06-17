import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import fa from '../i18n/fa'
import en from '../i18n/en'

type Lang = 'fa' | 'en'
type Theme = 'dark' | 'light'

interface AppState {
  lang: Lang
  theme: Theme
  t: typeof fa
  dir: 'rtl' | 'ltr'
  toggleLang: () => void
  toggleTheme: () => void
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      lang: 'fa',
      theme: 'dark',
      t: fa,
      dir: 'rtl',
      toggleLang: () => {
        const newLang = get().lang === 'fa' ? 'en' : 'fa'
        set({ lang: newLang, t: newLang === 'fa' ? fa : en, dir: newLang === 'fa' ? 'rtl' : 'ltr' })
        document.documentElement.lang = newLang
        document.documentElement.dir = newLang === 'fa' ? 'rtl' : 'ltr'
      },
      toggleTheme: () => {
        const newTheme = get().theme === 'dark' ? 'light' : 'dark'
        set({ theme: newTheme })
      },
    }),
    { name: 'nexa-app' }
  )
)
