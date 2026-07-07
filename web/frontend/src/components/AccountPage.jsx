import { useEffect, useState } from 'react'
import { useStore } from '../store.js'
import { t } from '../i18n.js'
import { api } from '../api.js'
import { navigate } from '../router.js'
import { fmtBRL } from '../plans.js'
import '../styles/plans.css'

function fmtDate(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleDateString() } catch { return iso }
}

// Área do cliente: plano ativo, uso do mês, próxima cobrança, upgrade/cancelar.
export default function AccountPage() {
  useStore(s => s.lang)
  const authUser = useStore(s => s.authUser)
  const billingMe = useStore(s => s.billingMe)
  const setBillingMe = useStore(s => s.setBillingMe)
  const logout = useStore(s => s.logout)
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    api.billingMe().then(setBillingMe).catch(() => {})
  }, [])

  const b = billingMe
  const statusKey = b?.status ? `acct_st_${b.status}` : null
  const planName = b?.plan === 'pro' ? t('plan_pro_name')
    : b?.plan === 'essencial' ? t('plan_essencial_name') : '—'
  const limit = b?.usage?.limit
  const used = b?.usage?.used ?? 0
  const pct = limit ? Math.min(100, Math.round(used / limit * 100)) : 0

  async function cancel() {
    if (busy || !window.confirm(t('acct_cancel_confirm'))) return
    setBusy(true)
    try {
      const res = await api.billingCancel()
      let m = t('acct_canceled_ok')
      if (res.refund_cents > 0) m += ` ${t('acct_refund')}: ${fmtBRL(res.refund_cents / 100)}.`
      setMsg(m)
      setBillingMe(await api.billingMe())
    } catch (e) {
      setMsg(String(e.message))
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
            <span className="pl-topbar-sep" />
            <a className="pl-back" href="/" onClick={e => { e.preventDefault(); navigate('/') }}>
              {t('acct_back_app')}
            </a>
          </div>
          <button className="pl-lang" onClick={logout} data-testid="acct-logout">{t('logout_btn')}</button>
        </div>

        <div className="pl-checkout">
          <h1>{t('acct_title')}</h1>

          <div className="pl-co-grid">
            <div className={`pl-co-card ${b?.plan === 'pro' ? 'pro' : 'essencial'}`} data-testid="acct-card">
              <div className="pl-co-label">{authUser?.email}</div>
              <div className="pl-co-row">
                {t('acct_plan')} <b data-testid="acct-plan">{planName}</b>
              </div>
              <div className="pl-co-row">
                {t('acct_status')} <b data-testid="acct-status">{statusKey ? t(statusKey) : '—'}</b>
              </div>
              {b?.status === 'trialing' && (
                <div className="pl-co-row">
                  {t('acct_trial_until')} <b>{fmtDate(b.trial_end)}</b>
                </div>
              )}
              {b?.current_period_end && (
                <div className="pl-co-row">
                  {t('acct_next_billing')} <b>{fmtDate(b.current_period_end)}</b>
                </div>
              )}

              <div className="pl-co-row total">
                {t('acct_usage')}
                <b data-testid="acct-usage">
                  {limit == null ? `${used} / ∞ ${t('acct_usage_unlim')}` : `${used} / ${limit}`}
                </b>
              </div>
              {limit != null && (
                <div className="pl-usage-bar">
                  <div className="pl-usage-fill" style={{ width: `${pct}%` }} data-over={pct >= 100} />
                </div>
              )}
            </div>

            <div className={`pl-co-card ${b?.plan === 'pro' ? 'pro' : 'essencial'}`}>
              <div className="pl-co-label">{t('rp_tools')}</div>
              <div className="pl-pay-options">
                <button className="pl-pay-opt" data-testid="acct-upgrade"
                        onClick={() => navigate('/planos')}>
                  <span className="pl-pay-radio" /> {t('acct_upgrade')}
                </button>
                {(b?.status === 'trialing' || b?.status === 'active') && (
                  <button className="pl-pay-opt" disabled={busy} data-testid="acct-cancel" onClick={cancel}>
                    <span className="pl-pay-radio" /> {t('acct_cancel')}
                  </button>
                )}
              </div>
              {msg && <div className="pl-co-note" data-testid="acct-msg">{msg}</div>}
              {b?.status === 'canceled' && b?.read_only_until && (
                <div className="pl-co-note">
                  {t('faq_projects_a')}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
