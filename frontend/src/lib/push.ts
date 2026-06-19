// اعلان‌های دستگاه (موبایل/دسکتاپ) — مبتنی بر Notification API + Service Worker.
// (بدون نیاز به سرور Push؛ هنگام باز بودن اپ، اعلان لحظه‌ای نمایش داده می‌شود.)

const SEEN_KEY = 'nexa_last_notif_id'

export async function ensureNotificationPermission(): Promise<NotificationPermission> {
  if (typeof Notification === 'undefined') return 'denied'
  let perm = Notification.permission
  if (perm === 'default') {
    try { perm = await Notification.requestPermission() } catch { perm = 'denied' }
  }
  if (perm === 'granted') {
    try { await subscribeToPush() } catch { /* ignore */ }
  }
  return perm
}

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = '='.repeat((4 - (base64.length % 4)) % 4)
  const b64 = (base64 + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = atob(b64)
  const arr = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i)
  return arr
}

/** اشتراکِ Web Push را می‌سازد و در سرور ثبت می‌کند (برای پوشِ واقعی روی گوشی). */
export async function subscribeToPush(): Promise<boolean> {
  try {
    const apiMod = await import('./api')
    const api = apiMod.default
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return false
    const reg = await navigator.serviceWorker.ready
    const { data } = await api.get('/notifications/vapid-public-key')
    const key = data?.key
    if (!key) return false
    let sub = await reg.pushManager.getSubscription()
    if (!sub) {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(key) as unknown as BufferSource,
      })
    }
    const j: any = sub.toJSON()
    await api.post('/notifications/subscribe', {
      endpoint: j.endpoint, p256dh: j.keys?.p256dh, auth: j.keys?.auth,
    })
    return true
  } catch {
    return false
  }
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
