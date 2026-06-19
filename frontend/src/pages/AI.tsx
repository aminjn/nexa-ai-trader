import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Brain,
  Zap,
  CheckCircle2,
  Send,
  Plus,
  Wifi,
  WifiOff,
  ChevronDown,
  Bot,
} from 'lucide-react'
import Layout from '../components/Layout'
import { useAppStore } from '../stores/appStore'
import { useAuthStore } from '../stores/authStore'
import api from '../lib/api'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  created_at: string
}

interface AIConnection {
  id: number
  provider: string
  status: 'connected' | 'disconnected'
}

const Spinner: React.FC<{ size?: number }> = ({ size = 20 }) => (
  <div
    style={{
      width: size,
      height: size,
      border: `2px solid var(--border)`,
      borderTopColor: 'var(--accent)',
      borderRadius: '50%',
      animation: 'spin 0.8s linear infinite',
      flexShrink: 0,
    }}
  />
)

const TypingDots: React.FC = () => (
  <div style={{ display: 'flex', gap: 5, alignItems: 'center', padding: '4px 0' }}>
    {[0, 1, 2].map((i) => (
      <span
        key={i}
        style={{
          width: 7,
          height: 7,
          borderRadius: '50%',
          background: 'var(--accent)',
          display: 'inline-block',
          animation: `pulse 1.1s ease-in-out ${i * 0.2}s infinite`,
        }}
      />
    ))}
  </div>
)

export default function AI() {
  const { t, dir } = useAppStore()
  const { isSuperAdmin } = useAuthStore()

  // AI Engine
  const [aiEnabled, setAiEnabled] = useState(false)
  const [togglingAI, setTogglingAI] = useState(false)

  // AI Connections (GapGPT)
  const [connections, setConnections] = useState<AIConnection[]>([])
  const [connLoading, setConnLoading] = useState(true)
  const [newApiKey, setNewApiKey] = useState('')
  const [addingConn, setAddingConn] = useState(false)
  const [connError, setConnError] = useState<string | null>(null)

  // GapGPT models
  const [models, setModels] = useState<string[]>([])
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [modelsLoading, setModelsLoading] = useState(false)
  const [modelsError, setModelsError] = useState<string | null>(null)
  const [savingModel, setSavingModel] = useState(false)

  // Chat
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [chatLoading, setChatLoading] = useState(true)
  const [inputText, setInputText] = useState('')
  const [sending, setSending] = useState(false)
  const chatEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-scroll
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Load chat history
  const loadChatHistory = useCallback(async () => {
    setChatLoading(true)
    try {
      const res = await api.get<ChatMessage[]>('/ai/chat/history')
      setMessages(res.data ?? [])
    } catch {
      // silent — chat starts empty
    } finally {
      setChatLoading(false)
    }
  }, [])

  // Load AI connections
  const loadConnections = useCallback(async () => {
    setConnLoading(true)
    try {
      const res = await api.get<AIConnection[]>('/ai/connections')
      setConnections(res.data ?? [])
    } catch {
      setConnections([])
    } finally {
      setConnLoading(false)
    }
  }, [])

  // Load GapGPT models (only works once a key is set)
  const loadModels = useCallback(async () => {
    setModelsLoading(true)
    setModelsError(null)
    try {
      const res = await api.get<{ models: string[]; selected: string }>('/ai/models')
      setModels(res.data.models ?? [])
      setSelectedModel(res.data.selected ?? '')
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setModelsError(e?.response?.data?.detail ?? 'دریافت مدل‌ها با خطا مواجه شد')
      setModels([])
    } finally {
      setModelsLoading(false)
    }
  }, [])

  // وضعیت ذخیره‌شده‌ی «اتصال AI به معاملات» را از سرور بخوان
  const loadTradingStatus = useCallback(async () => {
    try {
      const res = await api.get<{ ai_trading_enabled: boolean }>('/ai/trading-status')
      setAiEnabled(!!res.data?.ai_trading_enabled)
    } catch {
      // silent
    }
  }, [])

  useEffect(() => {
    loadChatHistory()
    loadConnections()
    loadModels()
    loadTradingStatus()
  }, [loadChatHistory, loadConnections, loadModels, loadTradingStatus])

  const handleSelectModel = async (model: string) => {
    setSelectedModel(model)
    setSavingModel(true)
    try {
      await api.put('/ai/model', { model })
    } catch {
      // silent
    } finally {
      setSavingModel(false)
    }
  }

  const handleToggleAI = async () => {
    setTogglingAI(true)
    try {
      const res = await api.put<{ ai_trading_enabled: boolean }>('/ai/toggle-trading')
      // وضعیت را از پاسخ سرور می‌گیریم تا همیشه با مقدار واقعی هماهنگ باشد
      setAiEnabled(!!res.data?.ai_trading_enabled)
    } catch {
      // revert silently
    } finally {
      setTogglingAI(false)
    }
  }

  const handleAddConnection = async () => {
    if (!newApiKey.trim()) return
    setAddingConn(true)
    setConnError(null)
    try {
      await api.post<AIConnection>('/ai/connections', {
        provider: 'GapGPT',
        api_key: newApiKey.trim(),
      })
      setNewApiKey('')
      await loadConnections()
      await loadModels()
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } }
      setConnError(e?.response?.data?.detail ?? 'افزودن اتصال با خطا مواجه شد')
    } finally {
      setAddingConn(false)
    }
  }

  const handleSendMessage = async () => {
    const text = inputText.trim()
    if (!text || sending) return

    const userMsg: ChatMessage = {
      role: 'user',
      content: text,
      created_at: new Date().toISOString(),
    }
    setMessages((prev) => [...prev, userMsg])
    setInputText('')
    setSending(true)

    try {
      const res = await api.post<ChatMessage>('/ai/chat', { message: text })
      setMessages((prev) => [...prev, res.data])
    } catch (e: any) {
      const detail = e?.response?.data?.detail
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: detail || 'متأسفم، نتوانستم درخواست شما را پردازش کنم. دوباره تلاش کنید.',
          created_at: new Date().toISOString(),
        },
      ])
    } finally {
      setSending(false)
      inputRef.current?.focus()
    }
  }

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  const formatTime = (iso: string) =>
    new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })

  const aiTasks = [
    { label: 'تحلیل روند بازار', freq: 'در هر چرخه ربات' },
    { label: 'ارزیابی ریسک', freq: 'هنگام هر معامله' },
    { label: 'تولید سیگنال', freq: 'طبق زمان‌بندی پنل' },
    { label: 'تصمیم خرید/فروش', freq: 'با مدل ML' },
  ]

  return (
    <Layout title={t.navAI} subtitle="وضعیت موتور عصبی و هوش بازار مبتنی بر هوش مصنوعی">
      <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 22 }}>

        {/* ─── Two-column layout ─── */}
        <div style={{ display: 'flex', gap: 22, alignItems: 'flex-start', flexWrap: 'wrap' }}>

          {/* ════════ LEFT COLUMN (فقط سوپر ادمین — کاربر عادی فقط چت‌بات را می‌بیند) ════════ */}
          {isSuperAdmin && (
          <div style={{ flex: 1.5, minWidth: 340, display: 'flex', flexDirection: 'column', gap: 22 }}>

            {/* Card 1 – AI Engine */}
            <div
              style={{
                background: 'var(--panel)',
                border: '1px solid var(--border)',
                borderRadius: 18,
                padding: 24,
              }}
            >
              {/* Header row */}
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 16, marginBlockEnd: 20 }}>
                {/* Icon with glow */}
                <div
                  style={{
                    width: 52,
                    height: 52,
                    borderRadius: 14,
                    background: 'rgba(75,224,255,0.1)',
                    border: '1px solid rgba(75,224,255,0.25)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    boxShadow: '0 0 24px rgba(75,224,255,0.15)',
                  }}
                >
                  <Brain size={26} color="var(--accent)" />
                </div>

                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                    <h2
                      style={{
                        margin: 0,
                        fontSize: 17,
                        fontWeight: 700,
                        color: 'var(--text)',
                        fontFamily: "'Space Grotesk', system-ui, sans-serif",
                      }}
                    >
                      {t.aiEngine}
                    </h2>
                    {/* Active badge */}
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 5,
                        padding: '3px 10px',
                        borderRadius: 999,
                        fontSize: 11,
                        fontWeight: 700,
                        background: 'rgba(75,224,170,0.15)',
                        color: 'var(--green)',
                        border: '1px solid rgba(75,224,170,0.25)',
                      }}
                    >
                      <span
                        style={{
                          width: 6,
                          height: 6,
                          borderRadius: '50%',
                          background: 'var(--green)',
                          boxShadow: '0 0 6px var(--green)',
                          animation: 'pulse 1.4s ease-in-out infinite',
                        }}
                      />
                      فعال
                    </span>
                  </div>
                  <p
                    style={{
                      margin: '4px 0 0',
                      fontSize: 14,
                      color: 'var(--accent)',
                      fontFamily: "'JetBrains Mono', monospace",
                      letterSpacing: '-0.3px',
                    }}
                  >
                    NEXA Neural Engine v2.1
                  </p>
                </div>
              </div>

              {/* Stats row */}
              <div
                style={{
                  display: 'flex',
                  gap: 12,
                  flexWrap: 'wrap',
                }}
              >
                {[
                  { label: 'پردازش', value: '۸۴۷ سیگنال در ثانیه' },
                  { label: 'تأخیر', value: '۱۲ms' },
                ].map(({ label, value }) => (
                  <div
                    key={label}
                    style={{
                      flex: 1,
                      minWidth: 140,
                      padding: '12px 16px',
                      borderRadius: 12,
                      background: 'var(--bg2)',
                      border: '1px solid var(--border)',
                    }}
                  >
                    <div style={{ fontSize: 11, color: 'var(--faint)', marginBlockEnd: 4 }}>{label}</div>
                    <div
                      style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 15,
                        fontWeight: 700,
                        color: 'var(--text)',
                      }}
                    >
                      {value}
                    </div>
                  </div>
                ))}
              </div>

              <p style={{ margin: '16px 0 0', fontSize: 13, color: 'var(--dim)', lineHeight: 1.6 }}>
                {t.aiRoleText}
              </p>
            </div>

            {/* Card 2 – Admin Controls (superAdmin only) */}
            {isSuperAdmin && (
              <div
                style={{
                  background: 'var(--panel)',
                  border: '1px solid var(--border)',
                  borderRadius: 18,
                  padding: 24,
                }}
              >
                <h3
                  style={{
                    margin: '0 0 18px',
                    fontSize: 15,
                    fontWeight: 700,
                    color: 'var(--text)',
                    fontFamily: "'Space Grotesk', system-ui, sans-serif",
                  }}
                >
                  {t.adminControls}
                </h3>

                {/* Toggle row */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBlockEnd: 16,
                    gap: 12,
                    flexWrap: 'wrap',
                  }}
                >
                  <div>
                    <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text)' }}>
                      {t.aiTradingLink}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--dim)', marginBlockStart: 2 }}>
                      اتصال سیگنال‌های هوش مصنوعی به موتور معاملات زنده
                    </div>
                  </div>

                  {/* Toggle switch */}
                  <button
                    className="toggle"
                    onClick={handleToggleAI}
                    disabled={togglingAI}
                    style={{
                      background: aiEnabled ? 'var(--accent)' : 'var(--bg3)',
                      opacity: togglingAI ? 0.7 : 1,
                    }}
                    aria-checked={aiEnabled}
                    role="switch"
                  >
                    <span
                      className="toggle-knob"
                      style={{
                        ...(dir === 'rtl'
                          ? { right: aiEnabled ? 3 : 'calc(100% - 25px)' }
                          : { left: aiEnabled ? 'calc(100% - 25px)' : 3 }),
                      }}
                    />
                  </button>
                </div>

                {/* Mode indicator banner */}
                <div
                  style={{
                    padding: '14px 18px',
                    borderRadius: 12,
                    background: aiEnabled
                      ? 'rgba(75,224,255,0.08)'
                      : 'rgba(255,255,255,0.04)',
                    border: `1px solid ${aiEnabled ? 'rgba(75,224,255,0.25)' : 'var(--border)'}`,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 10,
                  }}
                >
                  {aiEnabled ? (
                    <Zap size={16} color="var(--accent)" />
                  ) : (
                    <Bot size={16} color="var(--dim)" />
                  )}
                  <span
                    style={{
                      fontSize: 13,
                      fontWeight: 600,
                      color: aiEnabled ? 'var(--accent)' : 'var(--dim)',
                    }}
                  >
                    {aiEnabled ? t.aiModeAI : t.aiModeML}
                  </span>
                </div>
              </div>
            )}

            {/* Card 3 – AI Tasks */}
            <div
              style={{
                background: 'var(--panel)',
                border: '1px solid var(--border)',
                borderRadius: 18,
                padding: 24,
              }}
            >
              <h3
                style={{
                  margin: '0 0 18px',
                  fontSize: 15,
                  fontWeight: 700,
                  color: 'var(--text)',
                  fontFamily: "'Space Grotesk', system-ui, sans-serif",
                }}
              >
                {t.aiTasks}
              </h3>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {aiTasks.map(({ label, freq }) => (
                  <div
                    key={label}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '12px 16px',
                      borderRadius: 12,
                      background: 'var(--bg2)',
                      border: '1px solid var(--border)',
                      gap: 12,
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <CheckCircle2 size={16} color="var(--green)" />
                      <span style={{ fontSize: 13, color: 'var(--text)', fontWeight: 500 }}>
                        {label}
                      </span>
                    </div>
                    <span
                      style={{
                        fontSize: 11,
                        color: 'var(--faint)',
                        fontFamily: "'JetBrains Mono', monospace",
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {freq}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Card 4 – AI Connections */}
            <div
              style={{
                background: 'var(--panel)',
                border: '1px solid var(--border)',
                borderRadius: 18,
                padding: 24,
              }}
            >
              <div style={{ marginBlockEnd: 18 }}>
                <h3
                  style={{
                    margin: '0 0 4px',
                    fontSize: 15,
                    fontWeight: 700,
                    color: 'var(--text)',
                    fontFamily: "'Space Grotesk', system-ui, sans-serif",
                  }}
                >
                  {t.aiConnTitle}
                </h3>
                <p style={{ margin: 0, fontSize: 12, color: 'var(--dim)' }}>{t.aiConnSub}</p>
              </div>

              {/* Connection list */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBlockEnd: 18 }}>
                {connLoading ? (
                  <div style={{ display: 'flex', justifyContent: 'center', padding: '16px 0' }}>
                    <Spinner />
                  </div>
                ) : connections.length === 0 ? (
                  <p style={{ fontSize: 13, color: 'var(--faint)', textAlign: 'center', padding: '12px 0' }}>
                    هنوز هیچ سرویس هوش مصنوعی متصل نشده است.
                  </p>
                ) : (
                  connections.map((conn) => (
                    <div
                      key={conn.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '12px 16px',
                        borderRadius: 12,
                        background: 'var(--bg2)',
                        border: '1px solid var(--border)',
                        gap: 12,
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                        {conn.status === 'connected' ? (
                          <Wifi size={15} color="var(--green)" />
                        ) : (
                          <WifiOff size={15} color="var(--faint)" />
                        )}
                        <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text)' }}>
                          {conn.provider}
                        </span>
                      </div>
                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          padding: '3px 10px',
                          borderRadius: 999,
                          fontSize: 11,
                          fontWeight: 600,
                          background:
                            conn.status === 'connected'
                              ? 'rgba(75,224,170,0.15)'
                              : 'rgba(255,255,255,0.06)',
                          color:
                            conn.status === 'connected' ? 'var(--green)' : 'var(--faint)',
                        }}
                      >
                        {conn.status === 'connected' ? t.connected : t.disconnected}
                      </span>
                    </div>
                  ))
                )}
              </div>

              {/* Connect GapGPT key */}
              <div
                style={{
                  padding: '16px',
                  borderRadius: 12,
                  background: 'var(--bg2)',
                  border: '1px solid var(--border)',
                }}
              >
                <div style={{ fontSize: 12, color: 'var(--faint)', marginBlockEnd: 12 }}>
                  کلید API گپ‌جی‌پی‌تی
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {/* API Key input */}
                  <input
                    type="password"
                    placeholder="کلید گپ‌جی‌پی‌تی را وارد کنید"
                    value={newApiKey}
                    onChange={(e) => setNewApiKey(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleAddConnection()}
                    dir="ltr"
                  />

                  {connError && (
                    <p style={{ margin: 0, fontSize: 12, color: 'var(--red)' }}>{connError}</p>
                  )}

                  <button
                    onClick={handleAddConnection}
                    disabled={addingConn || !newApiKey.trim()}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      gap: 7,
                      padding: '11px 18px',
                      borderRadius: 11,
                      border: 'none',
                      background: 'var(--accent)',
                      color: '#05121a',
                      fontSize: 13,
                      fontWeight: 700,
                      cursor: addingConn || !newApiKey.trim() ? 'not-allowed' : 'pointer',
                      opacity: addingConn || !newApiKey.trim() ? 0.6 : 1,
                      fontFamily: "'Space Grotesk', system-ui, sans-serif",
                      transition: 'opacity 0.15s',
                    }}
                  >
                    {addingConn ? <Spinner size={16} /> : <Plus size={15} />}
                    اتصال و ذخیره کلید
                  </button>
                </div>
              </div>

              {/* GapGPT model picker */}
              <div
                style={{
                  marginBlockStart: 16,
                  padding: '16px',
                  borderRadius: 12,
                  background: 'var(--bg2)',
                  border: '1px solid var(--border)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBlockEnd: 12 }}>
                  <div style={{ fontSize: 12, color: 'var(--faint)' }}>
                    انتخاب مدل گپ‌جی‌پی‌تی
                  </div>
                  <button
                    onClick={loadModels}
                    disabled={modelsLoading}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 5,
                      background: 'none',
                      border: 'none',
                      color: 'var(--accent)',
                      fontSize: 11,
                      fontWeight: 600,
                      cursor: modelsLoading ? 'not-allowed' : 'pointer',
                      fontFamily: 'inherit',
                    }}
                  >
                    {modelsLoading ? <Spinner size={12} /> : null}
                    به‌روزرسانی لیست
                  </button>
                </div>

                {modelsError ? (
                  <p style={{ margin: 0, fontSize: 12, color: 'var(--faint)' }}>
                    {modelsError}
                  </p>
                ) : models.length === 0 ? (
                  <p style={{ margin: 0, fontSize: 12, color: 'var(--faint)' }}>
                    ابتدا کلید را وارد کنید تا لیست مدل‌ها بارگذاری شود.
                  </p>
                ) : (
                  <div style={{ position: 'relative' }}>
                    <select
                      value={selectedModel}
                      onChange={(e) => handleSelectModel(e.target.value)}
                      disabled={savingModel}
                      style={{
                        width: '100%',
                        appearance: 'none',
                        WebkitAppearance: 'none',
                        paddingInlineEnd: 36,
                      }}
                      dir="ltr"
                    >
                      {models.map((m) => (
                        <option key={m} value={m}>{m}</option>
                      ))}
                    </select>
                    <ChevronDown
                      size={14}
                      style={{
                        position: 'absolute',
                        insetBlockStart: '50%',
                        insetInlineEnd: 12,
                        transform: 'translateY(-50%)',
                        pointerEvents: 'none',
                        color: 'var(--faint)',
                      }}
                    />
                  </div>
                )}
                {selectedModel && !modelsError && models.length > 0 && (
                  <p style={{ margin: '10px 0 0', fontSize: 11, color: 'var(--green)' }}>
                    مدل فعال: {selectedModel}
                  </p>
                )}
              </div>
            </div>
          </div>
          )}

          {/* ════════ RIGHT COLUMN ════════ */}
          <div style={{ flex: 1, minWidth: 300 }}>

            {/* Card 5 – Chat Interface */}
            <div
              style={{
                background: 'var(--panel)',
                border: '1px solid var(--border)',
                borderRadius: 18,
                padding: 0,
                height: 640,
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
              }}
            >
              {/* Chat header */}
              <div
                style={{
                  padding: '18px 20px',
                  borderBlockEnd: '1px solid var(--border)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: 12,
                  flexShrink: 0,
                }}
              >
                <div
                  style={{
                    width: 38,
                    height: 38,
                    borderRadius: 10,
                    background: 'rgba(75,224,255,0.12)',
                    border: '1px solid rgba(75,224,255,0.2)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Bot size={18} color="var(--accent)" />
                </div>
                <div>
                  <div
                    style={{
                      fontSize: 15,
                      fontWeight: 700,
                      color: 'var(--text)',
                      fontFamily: "'Space Grotesk', system-ui, sans-serif",
                    }}
                  >
                    {t.aiChat}
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      color: 'var(--green)',
                      marginBlockStart: 1,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 4,
                    }}
                  >
                    <span
                      style={{
                        width: 5,
                        height: 5,
                        borderRadius: '50%',
                        background: 'var(--green)',
                        display: 'inline-block',
                        animation: 'pulse 1.4s ease-in-out infinite',
                      }}
                    />
                    NEXA Neural Engine · آنلاین
                  </div>
                </div>
              </div>

              {/* Message list */}
              <div
                style={{
                  flex: 1,
                  overflowY: 'auto',
                  padding: 16,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 12,
                }}
              >
                {chatLoading ? (
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flex: 1,
                    }}
                  >
                    <Spinner />
                  </div>
                ) : messages.length === 0 ? (
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flex: 1,
                      gap: 12,
                      color: 'var(--faint)',
                    }}
                  >
                    <Brain size={32} style={{ opacity: 0.3 }} color="var(--accent)" />
                    <p style={{ margin: 0, fontSize: 13, textAlign: 'center' }}>
                      درباره بازار، سیگنال‌ها یا استراتژی بپرسید.
                    </p>
                  </div>
                ) : (
                  messages.map((msg, idx) => {
                    const isUser = msg.role === 'user'
                    return (
                      <div
                        key={idx}
                        style={{
                          display: 'flex',
                          flexDirection: isUser ? 'row-reverse' : 'row',
                          alignItems: 'flex-end',
                          gap: 8,
                        }}
                      >
                        {/* Avatar */}
                        <div
                          style={{
                            width: 28,
                            height: 28,
                            borderRadius: '50%',
                            background: isUser
                              ? 'linear-gradient(135deg, var(--accent), var(--accent2))'
                              : 'rgba(75,224,255,0.15)',
                            border: isUser ? 'none' : '1px solid rgba(75,224,255,0.25)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                            fontSize: 11,
                            fontWeight: 700,
                            color: isUser ? '#05121a' : 'var(--accent)',
                          }}
                        >
                          {isUser ? 'شما' : <Bot size={13} />}
                        </div>

                        {/* Bubble */}
                        <div
                          style={{
                            maxWidth: '78%',
                          }}
                        >
                          <div
                            style={{
                              padding: '10px 14px',
                              borderRadius: isUser
                                ? '18px 18px 4px 18px'
                                : '18px 18px 18px 4px',
                              background: isUser
                                ? 'rgba(75,224,255,0.18)'
                                : 'var(--bg2)',
                              border: isUser
                                ? '1px solid rgba(75,224,255,0.2)'
                                : '1px solid var(--border)',
                              fontSize: 13,
                              color: 'var(--text)',
                              lineHeight: 1.55,
                              wordBreak: 'break-word',
                            }}
                          >
                            {msg.content}
                          </div>
                          <div
                            style={{
                              fontSize: 10,
                              color: 'var(--faint)',
                              marginBlockStart: 4,
                              textAlign: isUser ? 'end' : 'start',
                              fontFamily: "'JetBrains Mono', monospace",
                            }}
                          >
                            {formatTime(msg.created_at)}
                          </div>
                        </div>
                      </div>
                    )
                  })
                )}

                {/* Sending indicator */}
                {sending && (
                  <div
                    style={{
                      display: 'flex',
                      flexDirection: 'row',
                      alignItems: 'flex-end',
                      gap: 8,
                    }}
                  >
                    <div
                      style={{
                        width: 28,
                        height: 28,
                        borderRadius: '50%',
                        background: 'rgba(75,224,255,0.15)',
                        border: '1px solid rgba(75,224,255,0.25)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                        color: 'var(--accent)',
                      }}
                    >
                      <Bot size={13} />
                    </div>
                    <div
                      style={{
                        padding: '10px 14px',
                        borderRadius: '18px 18px 18px 4px',
                        background: 'var(--bg2)',
                        border: '1px solid var(--border)',
                      }}
                    >
                      <TypingDots />
                    </div>
                  </div>
                )}

                <div ref={chatEndRef} />
              </div>

              {/* Input area */}
              <div
                style={{
                  borderBlockStart: '1px solid var(--border)',
                  padding: 16,
                  display: 'flex',
                  gap: 8,
                  flexShrink: 0,
                }}
              >
                <input
                  ref={inputRef}
                  type="text"
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={handleInputKeyDown}
                  placeholder={t.chatPlaceholder}
                  disabled={sending}
                  style={{
                    flex: 1,
                    borderRadius: 12,
                    padding: '11px 14px',
                    fontSize: 13,
                    opacity: sending ? 0.7 : 1,
                  }}
                />
                <button
                  onClick={handleSendMessage}
                  disabled={sending || !inputText.trim()}
                  style={{
                    width: 44,
                    height: 44,
                    borderRadius: 12,
                    border: 'none',
                    background:
                      sending || !inputText.trim() ? 'var(--bg3)' : 'var(--accent)',
                    color:
                      sending || !inputText.trim() ? 'var(--faint)' : '#05121a',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor:
                      sending || !inputText.trim() ? 'not-allowed' : 'pointer',
                    flexShrink: 0,
                    transition: 'background 0.15s, color 0.15s',
                  }}
                  aria-label={t.send}
                >
                  {sending ? <Spinner size={16} /> : <Send size={16} />}
                </button>
              </div>
            </div>

          </div>
        </div>
      </div>
    </Layout>
  )
}
