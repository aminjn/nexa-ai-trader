import { useEffect, useState } from 'react'

/** آیا صفحه در اندازهٔ موبایل است؟ (پیش‌فرض آستانه ۸۲۰ پیکسل) */
export function useIsMobile(breakpoint = 820): boolean {
  const [isMobile, setIsMobile] = useState(
    typeof window !== 'undefined' ? window.innerWidth <= breakpoint : false
  )
  useEffect(() => {
    const onResize = () => setIsMobile(window.innerWidth <= breakpoint)
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [breakpoint])
  return isMobile
}
