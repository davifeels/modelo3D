import { useState } from 'react'
import { useStore } from '../store.js'
import { t, setLang } from '../i18n.js'
import { api } from '../api.js'
import { navigate, getQuery } from '../router.js'
import '../styles/plans.css'
import logo from '../assets/landing/logo.png'

// Redefinição de senha (/reset-password?token=…): o link chega por e-mail no
// fluxo "esqueci minha senha". Aqui o usuário define a NOVA senha; o token é
// de uso único e expira em 1h. Nenhuma senha é trocada sem passar por aqui.
export default function ResetPasswordPage() {
  const lang = useStore(s => s.lang)
  const storeSetLang = useStore(s => s.setLang)

  const token = getQuery().get('token') || ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)

  function toggleLang() {
    const nl = lang === 'pt' ? 'en' : 'pt'
    setLang(nl)
    storeSetLang(nl)
  }

  async function submit(e) {
    e.preventDefault()
    if (busy) return
    setError(null)
    if (password.length < 8) { setError(t('reset_err_short')); return }
    if (password !== confirm) { setError(t('reset_err_match')); return }
    setBusy(true)
    try {
      await api.resetPassword(token, password)
      setDone(true)
    } catch (_) {
      setError(t('reset_err_token'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="plans-root">
      <div className="pl-wrap">
        <div className="pl-topbar">
          <div className="pl-topbar-left">
            <img className="site-logo" src={logo} alt="ZefiroSplit" />
          </div>
          <button className="pl-lang" onClick={toggleLang}>{lang === 'pt' ? 'EN' : 'PT'}</button>
        </div>

        <div className="pl-login">
          <div className="pl-login-side">
            <div className="pl-hero-badge">🔑 ZefiroSplit</div>
            <h1>{t('reset_title')}</h1>
            <p>{t('reset_subtitle')}</p>
          </div>

          <div className="pl-co-card essencial pl-login-card" data-testid="reset-card">
            {!token ? (
              <div className="pl-login-error" data-testid="reset-notoken">{t('reset_err_token')}</div>
            ) : done ? (
              <div className="pl-login-form" data-testid="reset-done">
                <div className="pl-co-note">{t('reset_done')}</div>
                <button className="pl-co-pay-btn" onClick={() => navigate('/login')}
                        data-testid="reset-go-login">
                  {t('reset_go_login')}
                </button>
              </div>
            ) : (
              <form onSubmit={submit} className="pl-login-form">
                <label className="pl-field">
                  <span>{t('reset_new')}</span>
                  <input type="password" required minLength={8} value={password}
                         onChange={e => setPassword(e.target.value)}
                         autoComplete="new-password" data-testid="reset-password" />
                </label>
                <label className="pl-field">
                  <span>{t('reset_confirm')}</span>
                  <input type="password" required minLength={8} value={confirm}
                         onChange={e => setConfirm(e.target.value)}
                         autoComplete="new-password" data-testid="reset-confirm" />
                </label>
                {error && <div className="pl-login-error" data-testid="reset-error">{error}</div>}
                <button className="pl-co-pay-btn" type="submit" disabled={busy}
                        data-testid="reset-submit">
                  {busy ? t('login_loading') : t('reset_btn')}
                </button>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
