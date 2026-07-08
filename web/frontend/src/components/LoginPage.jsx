import { useState } from 'react'
import { useStore } from '../store.js'
import LogoMark from './LogoMark.jsx'
import { t, setLang } from '../i18n.js'
import { api } from '../api.js'
import { navigate } from '../router.js'
import '../styles/plans.css'

// Tela de login — SEM criação de conta: o acesso nasce exclusivamente da
// compra (/comprar). Aqui só existe: e-mail, senha, Entrar e Esqueci a senha.
export default function LoginPage() {
  const lang = useStore(s => s.lang)
  const storeSetLang = useStore(s => s.setLang)
  const setAuth = useStore(s => s.setAuth)
  const setBillingMe = useStore(s => s.setBillingMe)

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [info, setInfo] = useState(null)

  function toggleLang() {
    const nl = lang === 'pt' ? 'en' : 'pt'
    setLang(nl)
    storeSetLang(nl)
  }

  function friendlyError(e) {
    const d = String(e.message || '')
    if (d.includes('credenciais_invalidas')) return t('err_login')
    if (d.includes('conta_bloqueada')) return t('err_blocked')
    return t('err_login')
  }

  async function submit(e) {
    e.preventDefault()
    if (busy) return
    setError(null); setInfo(null)
    setBusy(true)
    try {
      const res = await api.login(email, password)
      setAuth(res.token, res.user)
      try { setBillingMe(await api.billingMe()) } catch (_) {}
      navigate('/')
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setBusy(false)
    }
  }

  async function forgot() {
    if (busy) return
    setError(null)
    if (!email) { setInfo(t('login_forgot_hint')); return }
    setBusy(true)
    try {
      await api.forgotPassword(email)
      setInfo(t('login_forgot_sent'))
    } catch (_) {
      setInfo(t('login_forgot_sent')) // resposta sempre genérica
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="plans-root">
      <div className="pl-wrap">
        <div className="pl-topbar">
          <div className="pl-topbar-left">
            <LogoMark />
          </div>
          <button className="pl-lang" onClick={toggleLang}>{lang === 'pt' ? 'EN' : 'PT'}</button>
        </div>

        <div className="pl-login">
          <div className="pl-login-side">
            <h1>{t('login_title')}</h1>
            <p>{t('login_subtitle')}</p>
          </div>

          <div className="pl-co-card essencial pl-login-card" data-testid="login-card">
            <form onSubmit={submit} className="pl-login-form">
              <label className="pl-field">
                <span>{t('login_email')}</span>
                <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                       autoComplete="email" data-testid="login-email" />
              </label>
              <label className="pl-field">
                <span>{t('login_password')}</span>
                <input type="password" required value={password}
                       onChange={e => setPassword(e.target.value)}
                       autoComplete="current-password" data-testid="login-password" />
              </label>

              {error && <div className="pl-login-error" data-testid="login-error">{error}</div>}
              {info && <div className="pl-co-note" data-testid="login-info">{info}</div>}

              <button className="pl-co-pay-btn" type="submit" disabled={busy} data-testid="login-submit">
                {busy ? t('login_loading') : t('login_btn')}
              </button>

              <button type="button" className="pl-link-btn" onClick={forgot}
                      data-testid="login-forgot">
                {t('login_forgot')}
              </button>

              <div className="pl-co-note">
                {t('login_no_account')}{' '}
                <a href="/comprar" onClick={e => { e.preventDefault(); navigate('/comprar') }}
                   data-testid="login-buy-link">
                  {t('login_buy_link')}
                </a>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
