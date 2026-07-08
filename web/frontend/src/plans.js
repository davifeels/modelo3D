// ── Dados dos planos de assinatura (fonte única: cards, tabela e checkout) ──
//
// Diferencial principal: Essencial fatia até 25 arquivos/mês; Pro é ilimitado.

export const PLANS = {
  essencial: {
    id: 'essencial',
    color: '#00C896',
    monthly: 19.90,
    annual: 179.90,        // cobrado à vista
    annualPerMonth: 14.99, // equivalente mensal do plano anual
  },
  pro: {
    id: 'pro',
    color: '#5B8EFF',
    monthly: 49.90,
    annual: 449.90,
    annualPerMonth: 37.49,
    popular: true,
  },
}

// ~25% nos dois planos (24,66% e 24,87%)
export function savingsPct(plan) {
  return Math.round((1 - plan.annual / (plan.monthly * 12)) * 100)
}

// Formatação manual para evitar o NBSP do toLocaleString (quebra asserts nos testes)
export function fmtBRL(v) {
  return 'R$ ' + v.toFixed(2).replace('.', ',')
}

// A compra acontece FORA do app principal (briefing da refatoração): /comprar
export function buyUrl(planoId, periodo) {
  return `/comprar?plano=${planoId}&periodo=${periodo}`
}

// ── Tabela de recursos ──────────────────────────────────────────────────────
// value: true (✔) | false (✕) | { chipKey } (pílula de limite, texto via i18n)
// highlight marca a linha/feature de maior diferença entre os planos.
export const FEATURES = [
  { key: 'feat_slices',    essencial: { chipKey: 'chip_25mo' },  pro: { chipKey: 'chip_unlimited' }, highlight: true },
  { key: 'feat_slicing',   essencial: true,                      pro: true },
  { key: 'feat_formats',   essencial: true,                      pro: true },
  { key: 'feat_gcode',     essencial: true,                      pro: true },
  { key: 'feat_updates',   essencial: true,                      pro: true },
  { key: 'feat_profiles',  essencial: { chipKey: 'chip_upto3' }, pro: { chipKey: 'chip_unlimited' } },
  { key: 'feat_history',   essencial: { chipKey: 'chip_30d' },   pro: { chipKey: 'chip_unlimited' } },
  { key: 'feat_extruders', essencial: false,                     pro: true },
  { key: 'feat_batch',     essencial: false,                     pro: true },
  { key: 'feat_api',       essencial: false,                     pro: { chipKey: 'chip_beta' } },
  { key: 'feat_cost',      essencial: false,                     pro: true },
  { key: 'feat_support',   essencial: { chipKey: 'chip_email' }, pro: { chipKey: 'chip_chat' } },
  { key: 'feat_early',     essencial: false,                     pro: true },
]

// Subconjunto exibido nos cards (a tabela completa lista FEATURES inteira)
export const CARD_FEATURES = {
  essencial: ['feat_slices', 'feat_slicing', 'feat_formats', 'feat_gcode',
              'feat_profiles', 'feat_history', 'feat_support',
              'feat_extruders', 'feat_batch', 'feat_api'],
  pro: ['feat_slices', 'feat_slicing', 'feat_profiles', 'feat_history',
        'feat_extruders', 'feat_batch', 'feat_api', 'feat_cost',
        'feat_support', 'feat_early'],
}

export const FAQ_KEYS = ['faq_limit', 'faq_change', 'faq_cancel_annual', 'faq_projects', 'faq_payment']
