import { Fragment, useEffect, useState } from 'react'
import { t } from '../i18n.js'
import { adminApi, getAdminToken, setAdminToken } from '../api.js'
import '../styles/plans.css'
import LogoMark from './LogoMark.jsx'

// Painel ADMINISTRATIVO (/admin) — autenticação própria (admin_users),
// completamente separada do login de clientes. Tabela de clientes com busca,
// reset de senha, envio de credenciais por e-mail (com log), bloqueio e
// histórico por cliente.

function fmtDate(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleString() } catch { return iso }
}

function AdminLogin({ onOk }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function submit(e) {
    e.preventDefault()
    if (busy) return
    setBusy(true); setError(null)
    try {
      const res = await adminApi.login(email, password)
      setAdminToken(res.token)
      onOk(res.admin)
    } catch (_) {
      setError(t('err_login'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="pl-login">
      <div className="pl-login-side">
        <div className="pl-hero-badge">🔐 {t('adm_title')}</div>
        <h1>{t('adm_title')}</h1>
      </div>
      <div className="pl-co-card pro pl-login-card" data-testid="adm-login-card">
        <form onSubmit={submit} className="pl-login-form">
          <label className="pl-field">
            <span>{t('login_email')}</span>
            <input type="email" required value={email} onChange={e => setEmail(e.target.value)}
                   data-testid="adm-email" />
          </label>
          <label className="pl-field">
            <span>{t('login_password')}</span>
            <input type="password" required value={password}
                   onChange={e => setPassword(e.target.value)} data-testid="adm-password" />
          </label>
          {error && <div className="pl-login-error" data-testid="adm-login-error">{error}</div>}
          <button className="pl-co-pay-btn" type="submit" disabled={busy} data-testid="adm-login-submit">
            {busy ? t('login_loading') : t('adm_login_btn')}
          </button>
        </form>
      </div>
    </div>
  )
}

function HistoryRow({ userId }) {
  const [hist, setHist] = useState(null)
  useEffect(() => {
    adminApi.history(userId).then(setHist).catch(() => {})
  }, [userId])
  if (!hist) return <tr><td colSpan={9} className="adm-hist">…</td></tr>
  return (
    <tr data-testid="adm-history-row">
      <td colSpan={9} className="adm-hist">
        <div className="adm-hist-grid">
          <div>
            <b>{t('adm_hist_compras')}</b>
            {hist.compras.length === 0 && <span>{t('adm_hist_none')}</span>}
            {hist.compras.map((c, i) => (
              <span key={i}>
                {fmtDate(c.data_compra)} — {c.plano}/{c.periodo} — R$ {(c.valor_cents / 100).toFixed(2)} — {c.status_pagamento}
              </span>
            ))}
          </div>
          <div>
            <b>{t('adm_hist_emails')}</b>
            {hist.emails.length === 0 && <span>{t('adm_hist_none')}</span>}
            {hist.emails.map((e, i) => (
              <span key={i}>{fmtDate(e.data_envio)} — {e.assunto} — {e.status}</span>
            ))}
          </div>
          <div>
            <b>{t('adm_hist_login')}</b>
            <span>{fmtDate(hist.user.ultimo_login)}</span>
            <b>{t('adm_col_status')}</b>
            <span>{hist.user.status} · {hist.assinatura.status || '—'}
              {hist.assinatura.fim_periodo ? ` até ${fmtDate(hist.assinatura.fim_periodo)}` : ''}</span>
          </div>
        </div>
      </td>
    </tr>
  )
}

export default function AdminPage() {
  const [admin, setAdmin] = useState(null)
  const [users, setUsers] = useState([])
  const [q, setQ] = useState('')
  const [field, setField] = useState('')
  const [openHist, setOpenHist] = useState(null)
  const [msg, setMsg] = useState(null)
  const [busy, setBusy] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [cNome, setCNome] = useState('')
  const [cEmail, setCEmail] = useState('')
  const [cTel, setCTel] = useState('')
  const [cPlano, setCPlano] = useState('')
  const [cPeriodo, setCPeriodo] = useState('mensal')

  async function refresh(query = q, f = field) {
    try {
      const res = await adminApi.users(query, f)
      setUsers(res.users)
    } catch (e) {
      if (e.status === 401) { setAdminToken(null); setAdmin(null) }
    }
  }

  // Boot: valida token admin salvo
  useEffect(() => {
    if (!getAdminToken()) return
    adminApi.me().then(res => { setAdmin(res.admin) }).catch(() => setAdminToken(null))
  }, [])
  useEffect(() => { if (admin) refresh() }, [admin])

  async function doReset(u) {
    if (busy || !window.confirm(`${t('adm_reset')}: ${u.email}?`)) return
    setBusy(true)
    try {
      const res = await adminApi.setPassword(u.id)
      setMsg(`${t('adm_reset_ok')} (${u.email}): ${res.temp_password}`)
      await refresh()
    } catch (e) { setMsg(String(e.message)) } finally { setBusy(false) }
  }

  // Definir uma senha ESPECÍFICA para qualquer cliente (pedido do painel);
  // difere do reset (🔑), que gera uma senha temporária aleatória.
  async function doSetPassword(u) {
    if (busy) return
    const pw = window.prompt(`${t('adm_setpw_prompt')} ${u.email}:`)
    if (pw == null) return
    if (pw.length < 6) { setMsg(t('adm_setpw_short')); return }
    setBusy(true)
    try {
      await adminApi.setPassword(u.id, pw)
      setMsg(`${t('adm_setpw_ok')} (${u.email})`)
      await refresh()
    } catch (e) { setMsg(String(e.message)) } finally { setBusy(false) }
  }

  async function doCreate(e) {
    e.preventDefault()
    if (busy) return
    setBusy(true)
    try {
      const res = await adminApi.createUser({
        nome: cNome, email: cEmail, telefone: cTel,
        plano: cPlano || null, periodo: cPeriodo,
      })
      setMsg(`${t('adm_created_ok')}: ${res.user.email} · ` +
             `${t('adm_col_senha')}: ${res.temp_password} · ` +
             `${t('adm_col_codigo')}: ${res.user.codigo_acesso}`)
      setShowCreate(false)
      setCNome(''); setCEmail(''); setCTel(''); setCPlano('')
      await refresh()
    } catch (e) {
      setMsg(String(e.message).includes('email_ja_cadastrado')
        ? t('adm_err_email_exists') : String(e.message))
    } finally { setBusy(false) }
  }

  async function doSend(u) {
    if (busy) return
    setBusy(true)
    try {
      const res = await adminApi.sendAccess(u.id)
      setMsg(`${t('adm_sent_ok')} → ${u.email} (${res.email_status})`)
      await refresh()
    } catch (e) { setMsg(String(e.message)) } finally { setBusy(false) }
  }

  async function doStatus(u) {
    if (busy) return
    setBusy(true)
    try {
      await adminApi.setStatus(u.id, u.status === 'bloqueado' ? 'ativo' : 'bloqueado')
      await refresh()
    } catch (e) { setMsg(String(e.message)) } finally { setBusy(false) }
  }

  function logout() {
    setAdminToken(null)
    setAdmin(null)
  }

  return (
    <div className="plans-root">
      <div className="pl-wrap adm-wrap">
        <div className="pl-topbar">
          <div className="pl-topbar-left">
            <LogoMark />
            <span className="pl-topbar-sep" />
            <span className="pl-back">{t('adm_title')}</span>
          </div>
          {admin && (
            <button className="pl-lang" onClick={logout} data-testid="adm-logout">
              {t('adm_logout')}
            </button>
          )}
        </div>

        {!admin ? <AdminLogin onOk={setAdmin} /> : (
          <div data-testid="adm-panel">
            {/* Busca com filtro por campo */}
            <div className="adm-toolbar">
              <input className="adm-search" placeholder={t('adm_search')} value={q}
                     data-testid="adm-search"
                     onChange={e => { setQ(e.target.value); refresh(e.target.value, field) }} />
              <select className="adm-select" value={field} data-testid="adm-field"
                      onChange={e => { setField(e.target.value); refresh(q, e.target.value) }}>
                <option value="">{t('adm_all_fields')}</option>
                <option value="nome">{t('adm_f_nome')}</option>
                <option value="email">{t('adm_f_email')}</option>
                <option value="telefone">{t('adm_f_telefone')}</option>
              </select>
              <button className="adm-create-btn" data-testid="adm-create-toggle"
                      onClick={() => setShowCreate(v => !v)}>
                {showCreate ? '✕' : '➕'} {t('adm_create')}
              </button>
            </div>

            {showCreate && (
              <form className="adm-create-form" onSubmit={doCreate} data-testid="adm-create-form">
                <label className="pl-field">
                  <span>{t('adm_f_nome')}</span>
                  <input required minLength={2} value={cNome}
                         onChange={e => setCNome(e.target.value)} data-testid="adm-c-nome" />
                </label>
                <label className="pl-field">
                  <span>{t('adm_f_email')}</span>
                  <input type="email" required value={cEmail}
                         onChange={e => setCEmail(e.target.value)} data-testid="adm-c-email" />
                </label>
                <label className="pl-field">
                  <span>{t('adm_f_telefone')}</span>
                  <input value={cTel} onChange={e => setCTel(e.target.value)}
                         data-testid="adm-c-telefone" />
                </label>
                <label className="pl-field">
                  <span>{t('adm_col_plano')}</span>
                  <select value={cPlano} onChange={e => setCPlano(e.target.value)}
                          data-testid="adm-c-plano">
                    <option value="">{t('adm_plan_none')}</option>
                    <option value="essencial">Essencial</option>
                    <option value="pro">Pro</option>
                  </select>
                </label>
                <label className="pl-field">
                  <span>{t('adm_periodo')}</span>
                  <select value={cPeriodo} disabled={!cPlano}
                          onChange={e => setCPeriodo(e.target.value)} data-testid="adm-c-periodo">
                    <option value="mensal">{t('adm_mensal')}</option>
                    <option value="anual">{t('adm_anual')}</option>
                  </select>
                </label>
                <button className="pl-co-pay-btn" type="submit" disabled={busy}
                        data-testid="adm-create-submit">
                  {t('adm_create_btn')}
                </button>
              </form>
            )}

            {msg && <div className="pl-co-note adm-msg" data-testid="adm-msg">{msg}</div>}

            <div className="pl-table-wrap">
              <table className="pl-table adm-table" data-testid="adm-table">
                <thead>
                  <tr>
                    <th>{t('adm_f_nome')}</th>
                    <th>{t('adm_f_email')}</th>
                    <th>{t('adm_f_telefone')}</th>
                    <th>{t('adm_col_plano')}</th>
                    <th>{t('adm_col_compra')}</th>
                    <th>{t('adm_col_status')}</th>
                    <th>{t('adm_col_codigo')}</th>
                    <th>{t('adm_col_senha')}</th>
                    <th>{t('adm_col_acoes')}</th>
                  </tr>
                </thead>
                <tbody>
                  {users.length === 0 && (
                    <tr><td colSpan={9}>{t('adm_empty')}</td></tr>
                  )}
                  {users.map(u => (
                    <Fragment key={u.id}>
                      <tr data-testid="adm-row" data-email={u.email}>
                        <td>{u.nome || '—'}</td>
                        <td>{u.email}</td>
                        <td>{u.telefone || '—'}</td>
                        <td>{u.plano || '—'}</td>
                        <td>{u.data_compra ? fmtDate(u.data_compra) : '—'}</td>
                        <td>
                          <span className={`adm-status ${u.status}`}>{u.status}</span>
                        </td>
                        <td className="adm-mono">{u.codigo_acesso || '—'}</td>
                        <td className="adm-mono">{u.temp_password || '—'}</td>
                        <td className="adm-actions">
                          <button onClick={() => doReset(u)} data-testid="adm-reset" disabled={busy}
                                  title={t('adm_reset')}>🔑</button>
                          <button onClick={() => doSetPassword(u)} data-testid="adm-setpw" disabled={busy}
                                  title={t('adm_setpw')}>✏️</button>
                          <button onClick={() => doSend(u)} data-testid="adm-send" disabled={busy}
                                  title={t('adm_send')}>✉️</button>
                          <button onClick={() => doStatus(u)} data-testid="adm-toggle-status" disabled={busy}
                                  title={u.status === 'bloqueado' ? t('adm_unblock') : t('adm_block')}>
                            {u.status === 'bloqueado' ? '🔓' : '🚫'}
                          </button>
                          <button onClick={() => setOpenHist(openHist === u.id ? null : u.id)}
                                  data-testid="adm-hist-btn" title={t('adm_history')}>📋</button>
                        </td>
                      </tr>
                      {openHist === u.id && <HistoryRow userId={u.id} />}
                    </Fragment>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
