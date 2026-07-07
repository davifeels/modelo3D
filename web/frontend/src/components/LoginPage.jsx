import { useState } from 'react'
import { useStore } from '../store.js'
import { t, setLang } from '../i18n.js'
import { api } from '../api.js'
import '../styles/plans.css'

// Tela de login/registro — porta de entrada do app (tudo exige autenticação).
// Registro inicia automaticamente o trial de 7 dias do Pro (sem cartão).
export default function LoginPage() {
  const lang = useStore(s => s.lang)
  const storeSetLang = useStore(s => s.setLang)
  const setAuth = useStore(s => s.setAuth)
  const setBillingMe = useStore(s => s.setBillingMe)

  const [mode, setMode] = useState('signin') // 'signin' | 'signup'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  function toggleLang() {
    const nl = lang === 'pt' ? 'en' : 'pt'
    setLang(nl)
    storeSetLang(nl)
  }

  function friendlyError(e) {
    const d = String(e.message || '')
    if (d.includes('credenciais_invalidas')) return t('err_login')
    if (d.includes('email_ja_cadastrado')) return t('err_email_taken')
    if (d.includes('email_invalido')) return t('err_email_invalid')
    if (e.status === 422) return mode === 'signup' ? t('err_password_short') : t('err_login')
    return t('err_generic')
  }

  async function submit(e) {
    e.preventDefault()
    if (busy) return
    setError(null)
    if (mode === 'signup' && password.length < 6) {
      setError(t('err_password_short'))
      return
    }
    setBusy(true)
    try {
      const res = mode === 'signup'
        ? await api.register(email, password, name)
        : await api.login(email, password)
      setAuth(res.token, res.user)
      // Carrega o estado de billing já autenticado (gate decide app × paywall)
      try { setBillingMe(await api.billingMe()) } catch (_) {}
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="plans-root">
      <div className="pl-wrap">
        <div className="pl-topbar">
          <div className="pl-topbar-left">
            <div className="pl-topbar-logo">Zefiro<span>Split</span></div>
          </div>
          <button className="pl-lang" onClick={toggleLang}>{lang === 'pt' ? 'EN' : 'PT'}</button>
        </div>

        <div className="pl-login">
          <div className="pl-login-side">
            <div className="pl-hero-badge">✦ {t('plans_hero_badge')}</div>
            <h1>{t('login_title')}</h1>
            <p>{t('login_subtitle')}</p>
          </div>

          <div className="pl-co-card essencial pl-login-card" data-testid="login-card">
            <div className="pl-login-tabs">
              <button className={mode === 'signin' ? 'active' : ''} data-testid="tab-signin"
                      onClick={() => { setMode('signin'); setError(null) }}>
                {t('login_tab_signin')}
              </button>
              <button className={mode === 'signup' ? 'active' : ''} data-testid="tab-signup"
                      onClick={() => { setMode('signup'); setError(null) }}>
                {t('login_tab_signup')}
              </button>
            </div>

            <form onSubmit={submit} className="pl-login-form">
              {mode === 'signup' && (
                <label className="pl-field">
                  <span>{t('login_name')}</span>
                  <input type="text" value={name} onChange={e => setName(e.target.value)}
                         autoComplete="name" data-testid="login-name" />
                </label>
              )}
              <label className="pl-field">
                <span>{t('login_email')}</span>
                <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                       autoComplete="email" data-testid="login-email" />
              </label>
              <label className="pl-field">
                <span>{t('login_password')}</span>
                <input type="password" required minLength={mode === 'signup' ? 6 : 1}
                       value={password} onChange={e => setPassword(e.target.value)}
                       autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                       data-testid="login-password" />
              </label>

              {error && <div className="pl-login-error" data-testid="login-error">{error}</div>}

              <button className="pl-co-pay-btn" type="submit" disabled={busy} data-testid="login-submit">
                {busy ? t('login_loading') : mode === 'signup' ? t('signup_btn') : t('login_btn')}
              </button>
              {mode === 'signup' && (
                <div className="pl-co-note">{t('signup_trial_note')}</div>
              )}
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
