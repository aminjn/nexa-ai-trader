// اعلان‌های دستگاه (موبایل/دسکتاپ) — مبتنی بر Notification API + Service Worker.
// (بدون نیاز به سرور Push؛ هنگام باز بودن اپ، اعلان لحظه‌ای نمایش داده می‌شود.)

const SEEN_KEY = 'nexa_last_notif_id'

export async function ensureNotificationPermission(): Promise<NotificationPermission> {
  if (typeof Notification === 'undefined') return 'denied'
  if (Notification.permission === 'granted' || Notification.permission === 'denied') return Notification.permission
  try { return await Notification.requestPermission() } catch { return 'denied' }
}

/** اگر اجازه قبلاً داده شده، اعلان دستگاه را نمایش می‌دهد (از طریق SW در صورت امکان). */
export async function showDeviceNotification(title: string, body: string, url = '/notifications') {
  if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return
  const opts: NotificationOptions = { body, icon: '/icon-192.png', badge: '/icon-192.png', data: { url } } as any
  try {
    if ('serviceWorker' in navigator) {
      const reg = await navigator.serviceWorker.getRegistration()
      if (reg) { await reg.showNotification(title, opts); return }
    }
    new Notification(title, opts)
  } catch { /* ignore */ }
}

export function getLastSeenId(): number {
  return Number(localStorage.getItem(SEEN_KEY) || 0)
}
export function setLastSeenId(id: number) {
  localStorage.setItem(SEEN_KEY, String(id))
}
