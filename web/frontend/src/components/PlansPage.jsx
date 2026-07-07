import { useState } from 'react'
import { useStore } from '../store.js'
import { t, tf, setLang } from '../i18n.js'
import { navigate } from '../router.js'
import { PLANS, FEATURES, CARD_FEATURES, FAQ_KEYS, fmtBRL, checkoutUrl } from '../plans.js'
import '../styles/plans.css'

function CheckIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
      <path d="M1.5 5.5L4 8l4.5-6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

function CrossIcon() {
  return (
    <svg width="9" height="9" viewBox="0 0 9 9" fill="none">
      <path d="M1.5 1.5l6 6M7.5 1.5l-6 6" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
    </svg>
  )
}

function ChevronIcon() {
  return (
    <svg className="pl-chev" width="14" height="14" viewBox="0 0 14 14" fill="none">
      <path d="M3 5l4 4 4-4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  )
}

// value: true | false | { chipKey }
function FeatureValue({ value, planId }) {
  if (value === false) return <span className="pl-no" aria-label="não incluído">✕</span>
  if (value === true) return <span className={`pl-yes ${planId}`} aria-label="incluído">✔</span>
  return <span className="pl-chip">{t(value.chipKey)}</span>
}

// Spotlight: expõe a posição do cursor como --mx/--my para o radial do CSS
function trackSpotlight(e) {
  const r = e.currentTarget.getBoundingClientRect()
  e.currentTarget.style.setProperty('--mx', `${e.clientX - r.left}px`)
  e.currentTarget.style.setProperty('--my', `${e.clientY - r.top}px`)
}

function PlanCard({ plan, periodo }) {
  const isAnnual = periodo === 'anual'
  const nameKey = plan.id === 'pro' ? 'plan_pro_name' : 'plan_essencial_name'
  const descKey = plan.id === 'pro' ? 'plan_pro_desc' : 'plan_essencial_desc'

  function goCheckout(e) {
    e.preventDefault()
    navigate(checkoutUrl(plan.id, periodo))
  }

  return (
    <div className={`pl-card ${plan.id}`} data-testid={`pl-card-${plan.id}`} onMouseMove={trackSpotlight}>
      {plan.popular && <span className="pl-popular">{t('plans_popular')}</span>}
      <div className="pl-card-name">{t(nameKey)}</div>
      <div className="pl-card-desc">{t(descKey)}</div>

      {/* key={periodo} remonta o preço ao alternar — replay da animação de pouso */}
      <div className="pl-price" data-testid={`pl-price-${plan.id}`} key={periodo}>
        <span className="pl-amount">{fmtBRL(isAnnual ? plan.annual : plan.monthly)}</span>
        <span className="pl-period">{isAnnual ? `/${t('plans_annual').toLowerCase()}` : t('plans_per_month')}</span>
      </div>
      <div className="pl-price-sub" data-testid={`pl-equiv-${plan.id}`} key={`sub-${periodo}`}>
        {isAnnual
          ? <>{t('plans_billed_once')} · <b>{tf('plans_equiv', { v: fmtBRL(plan.annualPerMonth) })}</b></>
          : null}
      </div>

      <a className="pl-cta" href={checkoutUrl(plan.id, periodo)} onClick={goCheckout}
         data-testid={`pl-cta-${plan.id}`}>
        {plan.trialDays ? t('plans_cta_trial') : t('plans_cta')}
      </a>
      <div className="pl-cta-sub">{plan.trialDays ? t('plans_no_card') : ' '}</div>

      <ul className="pl-features">
        {CARD_FEATURES[plan.id].map(key => {
          const feat = FEATURES.find(f => f.key === key)
          const value = feat[plan.id]
          const off = value === false
          return (
            <li key={key} className={feat.highlight ? 'hl' : off ? 'off' : ''}>
              <span className={`pl-ic ${off ? 'off' : 'on'}`}>{off ? <CrossIcon /> : <CheckIcon />}</span>
              {t(key)}
              {value !== true && value !== false && <span className="pl-chip">{t(value.chipKey)}</span>}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

function CompareTable({ periodo }) {
  const isAnnual = periodo === 'anual'
  return (
    <>
      <h2 className="pl-section-title">{t('plans_table_title')}</h2>
      <div className="pl-table-wrap">
        <table className="pl-table" data-testid="pl-table">
          <thead>
            <tr>
              <th>{t('plans_table_resource')}</th>
              <th className="essencial">{t('plan_essencial_name')}</th>
              <th className="pro">{t('plan_pro_name')}</th>
            </tr>
          </thead>
          <tbody>
            {FEATURES.map(f => (
              <tr key={f.key} className={f.highlight ? 'hl' : ''}>
                <td>{t(f.key)}</td>
                <td className="essencial"><FeatureValue value={f.essencial} planId="essencial" /></td>
                <td className="pro"><FeatureValue value={f.pro} planId="pro" /></td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td>{t('plans_table_price')}</td>
              {['essencial', 'pro'].map(id => {
                const p = PLANS[id]
                return (
                  <td key={id} data-testid={`pl-table-price-${id}`}>
                    <span className="pl-foot-price" key={`${id}-${periodo}`}>
                      {fmtBRL(isAnnual ? p.annualPerMonth : p.monthly)}{t('plans_per_month')}
                    </span>
                    {isAnnual && (
                      <span className="pl-foot-note">{tf('plans_table_annual_note', { v: fmtBRL(p.annual) })}</span>
                    )}
                  </td>
                )
              })}
            </tr>
          </tfoot>
        </table>
      </div>
    </>
  )
}

function Faq() {
  const [open, setOpen] = useState(null) // apenas uma pergunta aberta por vez

  return (
    <div className="pl-faq-grid">
      {/* Coluna lateral: título + nota de pagamento */}
      <div className="pl-faq-intro">
        <h2 className="pl-section-title">{t('plans_faq_title')}</h2>
        <div className="pl-footnote">
          {t('co_pay_card')} (Visa · Mastercard · Elo)
          <br />
          PIX / {t('co_pay_boleto')} — {t('co_pay_annual_only')}
        </div>
      </div>

      <div className="pl-faq" data-testid="pl-faq">
        {FAQ_KEYS.map(key => {
          const isOpen = open === key
          return (
            <div key={key} className={`pl-faq-item ${isOpen ? 'open' : ''}`} data-testid={`pl-faq-${key}`}>
              <button className="pl-faq-q" aria-expanded={isOpen}
                      onClick={() => setOpen(isOpen ? null : key)}>
                {t(`${key}_q`)}
                <ChevronIcon />
              </button>
              <div className="pl-faq-a">
                <p>{t(`${key}_a`)}</p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// paywall=true: usuário logado sem plano ativo — sem "voltar ao app", com aviso e Sair
export default function PlansPage({ paywall = false }) {
  const lang = useStore(s => s.lang) // re-render ao trocar idioma
  const storeSetLang = useStore(s => s.setLang)
  const authUser = useStore(s => s.authUser)
  const logout = useStore(s => s.logout)
  const [periodo, setPeriodo] = useState('mensal')
  const isAnnual = periodo === 'anual'

  function toggleLang() {
    const nl = lang === 'pt' ? 'en' : 'pt'
    setLang(nl)
    storeSetLang(nl)
  }

  return (
    <div className="plans-root">
      <div className="pl-wrap">
        {/* Topbar: logo + voltar à esquerda, idioma à direita */}
        <div className="pl-topbar">
          <div className="pl-topbar-left">
            <div className="pl-topbar-logo">Zefiro<span>Split</span></div>
            {!paywall && (
              <>
                <span className="pl-topbar-sep" />
                <a className="pl-back" href="/" onClick={e => { e.preventDefault(); navigate('/') }}>
                  {t('plans_back')}
                </a>
              </>
            )}
          </div>
          <div className="pl-topbar-left">
            {paywall && (
              <button className="pl-lang" onClick={logout} data-testid="paywall-logout">
                {t('logout_btn')}
              </button>
            )}
            <button className="pl-lang" onClick={toggleLang}>{lang === 'pt' ? 'EN' : 'PT'}</button>
          </div>
        </div>

        {paywall && (
          <div className="pl-paywall-banner" data-testid="paywall-banner">
            <b>{t('paywall_notice')}</b>
            {authUser?.email && (
              <span>{t('paywall_logged_as')} <b>{authUser.email}</b></span>
            )}
          </div>
        )}

        {/* Hero em duas colunas: texto à esquerda, toggle ancorado à direita */}
        <div className="pl-hero-row">
          <div className="pl-hero">
            <div className="pl-hero-badge">✦ {t('plans_hero_badge')}</div>
            <h1>{t('plans_title')}</h1>
            <p>{t('plans_subtitle')}</p>
          </div>

          <div className="pl-toggle-row">
            <div className="pl-toggle" role="tablist" data-period={periodo}>
              <button className={!isAnnual ? 'active' : ''} data-testid="pl-toggle-mensal"
                      onClick={() => setPeriodo('mensal')}>
                {t('plans_monthly')}
              </button>
              <button className={isAnnual ? 'active' : ''} data-testid="pl-toggle-anual"
                      onClick={() => setPeriodo('anual')}>
                {t('plans_annual')}
                <span className="pl-tag">{t('plans_annual_tag')}</span>
              </button>
            </div>
            {isAnnual && (
              <div className="pl-save-pill" data-testid="pl-save-pill">
                {t('plans_save_pill')}
              </div>
            )}
          </div>
        </div>

        <div className="pl-cards">
          <PlanCard plan={PLANS.essencial} periodo={periodo} />
          <PlanCard plan={PLANS.pro} periodo={periodo} />
        </div>

        <CompareTable periodo={periodo} />
        <Faq />
      </div>
    </div>
  )
}
