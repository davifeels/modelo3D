import { useState } from 'react'
import { useStore } from '../store.js'
import { t } from '../i18n.js'
import { api } from '../api.js'
import { navigate, getQuery } from '../router.js'
import { PLANS, fmtBRL } from '../plans.js'
import '../styles/plans.css'

// Spotlight: expõe a posição do cursor como --mx/--my para o radial do CSS
function trackSpotlight(e) {
  const r = e.currentTarget.getBoundingClientRect()
  e.currentTarget.style.setProperty('--mx', `${e.clientX - r.left}px`)
  e.currentTarget.style.setProperty('--my', `${e.clientY - r.top}px`)
}

// Fluxo de checkout — o plano e o período chegam pré-selecionados via URL
// (?plano=essencial|pro&periodo=mensal|anual), conforme o briefing.
// A cobrança em si depende do gateway de pagamento (a definir) — o botão
// final fica desabilitado até essa integração existir.
export default function CheckoutPage() {
  useStore(s => s.lang) // re-render ao trocar idioma

  const q = getQuery()
  const planoId = PLANS[q.get('plano')] ? q.get('plano') : 'essencial'
  const periodo = q.get('periodo') === 'anual' ? 'anual' : 'mensal'
  const plan = PLANS[planoId]
  const isAnnual = periodo === 'anual'

  const [payMethod, setPayMethod] = useState('card')
  const [busy, setBusy] = useState(false)
  const [payMsg, setPayMsg] = useState(null)
  const authToken = useStore(s => s.authToken)

  const planName = t(planoId === 'pro' ? 'plan_pro_name' : 'plan_essencial_name')
  const total = isAnnual ? plan.annual : plan.monthly

  // Dispara o checkout no backend; sem gateway configurado o backend responde
  // 501 e mostramos a nota. Com gateway real, redireciona para checkout_url.
  async function pay() {
    if (busy) return
    if (!authToken) { navigate('/') ; return } // paga-se logado — vai para o login
    setBusy(true)
    setPayMsg(null)
    try {
      const res = await api.billingCheckout(planoId, periodo, payMethod)
      if (res.checkout_url) window.location.href = res.checkout_url
    } catch (e) {
      setPayMsg(e.status === 501 ? t('co_gateway_note') : String(e.message))
    } finally {
      setBusy(false)
    }
  }

  // Regra de negócio: PIX e boleto apenas no plano anual (cobrança única à vista)
  const payOptions = [
    { id: 'card',   label: t('co_pay_card'),   sub: t('co_pay_card_sub'),     enabled: true },
    { id: 'pix',    label: t('co_pay_pix'),    sub: isAnnual ? '' : t('co_pay_annual_only'), enabled: isAnnual },
    { id: 'boleto', label: t('co_pay_boleto'), sub: isAnnual ? '' : t('co_pay_annual_only'), enabled: isAnnual },
  ]

  return (
    <div className="plans-root">
      <div className="pl-wrap">
        <div className="pl-topbar">
          <div className="pl-topbar-left">
            <div className="pl-topbar-logo">Zefiro<span>Split</span></div>
            <span className="pl-topbar-sep" />
            <a className="pl-back" href="/planos" onClick={e => { e.preventDefault(); navigate('/planos') }}>
              {t('co_back')}
            </a>
          </div>
          <span style={{ width: 42 }} />
        </div>

        <div className="pl-checkout">
          <h1>{t('co_title')}</h1>

          <div className="pl-co-grid">
          {/* Resumo do pedido */}
          <div className={`pl-co-card ${planoId}`} data-testid="co-summary" onMouseMove={trackSpotlight}>
            <div className="pl-co-label">{t('co_summary')}</div>
            <div className="pl-co-row">
              {t('co_plan')} <b data-testid="co-plan">{planName}</b>
            </div>
            <div className="pl-co-row">
              {t('co_period')} <b data-testid="co-period">{t(isAnnual ? 'co_period_anual' : 'co_period_mensal')}</b>
            </div>
            <div className="pl-co-row total">
              {t('co_total')} <b data-testid="co-total">{fmtBRL(total)}</b>
            </div>
            {isAnnual && (
              <div className="pl-co-equiv">≈ {fmtBRL(plan.annualPerMonth)}{t('plans_per_month')}</div>
            )}
            {plan.trialDays && (
              <div className="pl-co-trial" data-testid="co-trial">✦ {t('co_trial_note')}</div>
            )}
          </div>

          {/* Forma de pagamento */}
          <div className={`pl-co-card ${planoId}`} onMouseMove={trackSpotlight}>
            <div className="pl-co-label">{t('co_pay_title')}</div>
            <div className="pl-pay-options">
              {payOptions.map(opt => (
                <button key={opt.id}
                        className={`pl-pay-opt ${payMethod === opt.id ? 'selected' : ''}`}
                        disabled={!opt.enabled}
                        data-testid={`co-pay-${opt.id}`}
                        onClick={() => setPayMethod(opt.id)}>
                  <span className="pl-pay-radio" />
                  {opt.label}
                  {opt.sub && <span className="pl-pay-sub">{opt.sub}</span>}
                </button>
              ))}
            </div>
            <button className="pl-co-pay-btn" disabled={busy} onClick={pay} data-testid="co-pay-btn">
              {t('co_pay_btn')}
            </button>
            {payMsg && <div className="pl-co-note" data-testid="co-pay-msg" style={{ color: 'var(--pl-text2)' }}>{payMsg}</div>}
            <div className="pl-co-note">
              {isAnnual && t('co_refund_note')}
            </div>
          </div>
          </div>
        </div>
      </div>
    </div>
  )
}
