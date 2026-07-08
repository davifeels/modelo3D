import { useState } from 'react'
import { useStore } from '../store.js'
import LogoMark from './LogoMark.jsx'
import { t, tf, setLang } from '../i18n.js'
import { api } from '../api.js'
import { navigate, getQuery } from '../router.js'
import { PLANS, fmtBRL } from '../plans.js'
import '../styles/plans.css'

// Área de COMPRA DE ACESSO — módulo separado do app principal (público).
// Lista os produtos, coleta nome/e-mail/telefone e confirma a compra; o
// backend cria o cadastro automaticamente (senha temporária + código de
// acesso) e o cliente recebe as credenciais por e-mail. Sem cadastro manual.
export default function PurchasePage() {
  const lang = useStore(s => s.lang)
  const storeSetLang = useStore(s => s.setLang)

  const q = getQuery()
  const [plano, setPlano] = useState(PLANS[q.get('plano')] ? q.get('plano') : 'pro')
  const [periodo, setPeriodo] = useState(q.get('periodo') === 'anual' ? 'anual' : 'mensal')
  const [nome, setNome] = useState('')
  const [email, setEmail] = useState('')
  const [telefone, setTelefone] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(null) // resposta da compra

  const isAnnual = periodo === 'anual'
  const plan = PLANS[plano]
  const total = isAnnual ? plan.annual : plan.monthly

  function toggleLang() {
    const nl = lang === 'pt' ? 'en' : 'pt'
    setLang(nl)
    storeSetLang(nl)
  }

  function friendlyError(e) {
    const d = String(e.message || '')
    if (d.includes('email_invalido')) return t('err_email_invalid')
    if (d.includes('telefone_invalido')) return t('buy_err_telefone')
    if (d.includes('conta_bloqueada')) return t('err_blocked')
    return t('buy_err_generic')
  }

  async function submit(e) {
    e.preventDefault()
    if (busy) return
    setError(null)
    setBusy(true)
    try {
      const res = await api.purchase({ nome, email, telefone, plano, periodo })
      if (res.checkout_url) { window.location.href = res.checkout_url; return }
      setDone(res)
    } catch (err) {
      setError(friendlyError(err))
    } finally {
      setBusy(false)
    }
  }

  if (done) {
    return (
      <div className="plans-root">
        <header className="ld-topbar">
          <div className="ld-topbar-inner">
            <LogoMark />
          </div>
        </header>
        <div className="pl-wrap">
          <div className="pl-checkout">
            <div className="pl-co-card pro pl-buy-success" data-testid="buy-success">
              <h1>{t('buy_success_title')}</h1>
              <p>{done.renewed ? t('buy_renewed_msg') : t('buy_success_msg')}</p>
              <button className="pl-co-pay-btn" data-testid="buy-go-login"
                      onClick={() => navigate('/login')}>
                {t('buy_go_login')}
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="plans-root">
      {/* Header sticky full-width */}
      <header className="ld-topbar">
        <div className="ld-topbar-inner">
          <LogoMark />
          <div className="ld-nav" style={{ gap: 16 }}>
            <a className="pl-back" href="/" onClick={e => { e.preventDefault(); navigate('/') }}>
              ← {t('buy_back')}
            </a>
            <button className="pl-lang" onClick={toggleLang}>{lang === 'pt' ? 'EN' : 'PT'}</button>
          </div>
        </div>
      </header>

      <div className="pl-wrap">
        <div className="pl-checkout">
          <h1>{t('buy_title')}</h1>
          <p className="ld-plans-sub">{t('buy_subtitle')}</p>

          {/* Toggle mensal/anual */}
          <div className="pl-toggle" role="tablist" data-period={periodo} style={{ marginBottom: 18 }}>
            <button className={!isAnnual ? 'active' : ''} data-testid="buy-toggle-mensal"
                    onClick={() => setPeriodo('mensal')}>{t('plans_monthly')}</button>
            <button className={isAnnual ? 'active' : ''} data-testid="buy-toggle-anual"
                    onClick={() => setPeriodo('anual')}>
              {t('plans_annual')}<span className="pl-tag">{t('plans_annual_tag')}</span>
            </button>
          </div>

          <div className="pl-co-grid">
            {/* Produtos disponíveis */}
            <div>
              {['essencial', 'pro'].map(id => {
                const p = PLANS[id]
                const price = isAnnual ? p.annual : p.monthly
                return (
                  <button key={id}
                          className={`pl-co-card ${id} pl-buy-product ${plano === id ? 'selected' : ''}`}
                          data-testid={`buy-plan-${id}`}
                          onClick={() => setPlano(id)}>
                    <span className="pl-pay-radio" data-on={plano === id} />
                    <span className="pl-buy-product-info">
                      <b>{t(id === 'pro' ? 'plan_pro_name' : 'plan_essencial_name')}</b>
                      <small>{t(id === 'pro' ? 'plan_pro_desc' : 'plan_essencial_desc')}</small>
                      <small className="pl-chip">
                        {t(id === 'pro' ? 'chip_unlimited' : 'chip_25mo')}
                      </small>
                    </span>
                    <span className="pl-buy-product-price">
                      {fmtBRL(price)}<small>{isAnnual ? `/${t('plans_annual').toLowerCase()}` : t('plans_per_month')}</small>
                      {isAnnual && <small>{tf('plans_equiv', { v: fmtBRL(p.annualPerMonth) })}</small>}
                    </span>
                  </button>
                )
              })}

              <div className="pl-co-card pro" style={{ marginTop: 12 }}>
                <div className="pl-co-row total">
                  {t('co_total')} <b data-testid="buy-total">{fmtBRL(total)}</b>
                </div>
                {isAnnual && <div className="pl-co-note">{t('co_refund_note')}</div>}
              </div>
            </div>

            {/* Formulário: nome, e-mail, telefone (requisito da tela de compra) */}
            <form className={`pl-co-card ${plano} pl-login-form`} onSubmit={submit}
                  data-testid="buy-form">
              <div className="pl-co-label">{t('buy_your_data')}</div>
              <label className="pl-field">
                <span>{t('buy_nome')}</span>
                <input type="text" required minLength={2} value={nome}
                       onChange={e => setNome(e.target.value)}
                       autoComplete="name" data-testid="buy-nome" />
              </label>
              <label className="pl-field">
                <span>{t('login_email')}</span>
                <input type="email" required value={email}
                       onChange={e => setEmail(e.target.value)}
                       autoComplete="email" data-testid="buy-email" />
              </label>
              <label className="pl-field">
                <span>{t('buy_telefone')}</span>
                <input type="tel" required minLength={8} value={telefone}
                       onChange={e => setTelefone(e.target.value)}
                       placeholder="(11) 99999-9999"
                       autoComplete="tel" data-testid="buy-telefone" />
              </label>

              {error && <div className="pl-login-error" data-testid="buy-error">{error}</div>}

              <button className="pl-co-pay-btn" type="submit" disabled={busy}
                      data-testid="buy-submit">
                {busy ? t('buy_processing') : `${t('buy_confirm')} — ${fmtBRL(total)}`}
              </button>
              <div className="pl-co-note">{t('buy_success_msg')}</div>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}
