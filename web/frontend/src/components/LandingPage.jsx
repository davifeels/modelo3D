import { useStore } from '../store.js'
import { t, tf, setLang } from '../i18n.js'
import { navigate } from '../router.js'
import { PLANS, fmtBRL } from '../plans.js'
import '../styles/plans.css'
import shotApp from '../assets/landing/app-full.png'
import shotPanel from '../assets/landing/panel-tools.png'
import shotPanel2 from '../assets/landing/panel-tools-2.png'
import LogoMark from './LogoMark.jsx'

function BuyButton({ testid }) {
  return (
    <div className="ld-buy-wrap">
      <a className="pl-co-pay-btn ld-buy" href="/comprar" data-testid={testid}
         onClick={e => { e.preventDefault(); navigate('/comprar') }}>
        {t('ld_cta_buy')}
      </a>
      <div className="pl-cta-sub">{t('ld_cta_sub')}</div>
    </div>
  )
}

function Faq() {
  const KEYS = ['faq_limit', 'faq_change', 'faq_cancel_annual', 'faq_projects', 'faq_payment']
  return (
    <div className="pl-faq ld-faq" data-testid="ld-faq" id="faq">
      <h2 className="pl-section-title">{t('plans_faq_title')}</h2>
      {KEYS.map(key => (
        <details key={key} className="ld-faq-item">
          <summary>{t(`${key}_q`)}</summary>
          <p>{t(`${key}_a`)}</p>
        </details>
      ))}
    </div>
  )
}

export default function LandingPage() {
  const lang = useStore(s => s.lang)
  const storeSetLang = useStore(s => s.setLang)

  function toggleLang() {
    const nl = lang === 'pt' ? 'en' : 'pt'
    setLang(nl)
    storeSetLang(nl)
  }

  const benefits = [
    ['ld_b1_t', 'ld_b1_d', '🖨️'],
    ['ld_b2_t', 'ld_b2_d', '🧩'],
    ['ld_b3_t', 'ld_b3_d', '🖌️'],
    ['ld_b4_t', 'ld_b4_d', '🌐'],
  ]

  const featCards = [
    { k: 'ld_f1', ic: '✂️' },
    { k: 'ld_f2', ic: '🧩' },
    { k: 'ld_f3', ic: '🖌️' },
    { k: 'ld_f4', ic: '📐' },
    { k: 'ld_f5', ic: '📦' },
    { k: 'ld_f6', ic: '🌐' },
  ]

  const testimonials = [
    ['ld_t1_n', 'ld_t1_d'],
    ['ld_t2_n', 'ld_t2_d'],
    ['ld_t3_n', 'ld_t3_d'],
  ]

  return (
    <div className="plans-root ld-root" data-testid="landing">

      {/* ── Navbar — fixed full-width, fora do pl-wrap ─────────── */}
      <header className="ld-topbar">
        <div className="ld-topbar-inner">
          <LogoMark />
          <div className="ld-nav">
            <a href="#features">{t('ld_nav_features')}</a>
            <a href="#planos">{t('ld_nav_plans')}</a>
            <a href="#faq">{t('ld_nav_faq')}</a>
            <button className="pl-lang" onClick={toggleLang}>{lang === 'pt' ? 'EN' : 'PT'}</button>
            <a className="pl-lang ld-login-link" href="/login" data-testid="ld-login"
               onClick={e => { e.preventDefault(); navigate('/login') }}>
              {t('ld_nav_login')}
            </a>
          </div>
        </div>
      </header>

      <div className="pl-wrap">

        {/* ── Hero + glow ──────────────────────────────────────── */}
        <div className="ld-hero-wrap">
          <div className="ld-glow-orb" aria-hidden="true" />
          <div className="ld-glow-orb ld-glow-orb-b" aria-hidden="true" />

          <div className="ld-hero">
            <div className="pl-hero-badge">✂️ 3D Mesh Splitter</div>
            <h1 data-testid="ld-title">{t('ld_hero_title')}</h1>
            <p className="ld-hero-sub">{t('ld_hero_sub')}</p>
            <BuyButton testid="ld-buy-hero" />

            {/* Social proof */}
            <div className="ld-social-row">
              <div className="ld-stars-sm">★★★★★</div>
              <span>Makers já usando para imprimir modelos grandes</span>
            </div>
          </div>

          {/* App screenshot em moldura */}
          <div className="ld-hero-shot">
            <div className="ld-frame">
              <div className="ld-frame-bar"><i /><i /><i /></div>
              <img src={shotApp} alt="ZefiroSplit — fatiador 3D no navegador" loading="eager" />
            </div>
            <div className="ld-shot-caption">{t('ld_shot_caption')}</div>
          </div>
        </div>

        {/* ── Stats ─────────────────────────────────────────────── */}
        <div className="ld-stats">
          {[1, 2, 3, 4].map(i => (
            <div className="ld-stat" key={i}>
              <b>{t(`ld_stat${i}_v`)}</b>
              <span>{t(`ld_stat${i}_l`)}</span>
            </div>
          ))}
        </div>

        {/* ── Benefícios ────────────────────────────────────────── */}
        <h2 className="pl-section-title">{t('ld_benefits_title')}</h2>
        <div className="ld-grid4">
          {benefits.map(([ti, de, ic]) => (
            <div className="ld-benefit-card" key={ti}>
              <div className="ld-benefit-ic">{ic}</div>
              <b>{t(ti)}</b>
              <p>{t(de)}</p>
            </div>
          ))}
        </div>

        <div className="ld-sep" />

        {/* ── Por dentro da ferramenta ──────────────────────────── */}
        <h2 className="pl-section-title" id="inside">{t('ld_inside_title')}</h2>
        <div className="ld-inside">
          <div className="ld-inside-txt">
            <h3>{t('ld_in1_t')}</h3>
            <p>{t('ld_in1_d')}</p>
            <ul className="pl-features ld-inside-list">
              {[1, 2, 3].map(i => (
                <li key={i}><span className="pl-ic on">✔</span>{t(`ld_in1_b${i}`)}</li>
              ))}
            </ul>
          </div>
          <div className="ld-inside-shot">
            <img src={shotPanel} alt="Painel de seleção manual — pincel, conta-gotas e borracha" loading="lazy" />
          </div>
        </div>
        <div className="ld-inside rev">
          <div className="ld-inside-shot">
            <img src={shotPanel2} alt="Sensibilidade do conta-gotas — ângulo de parada e raio de expansão" loading="lazy" />
          </div>
          <div className="ld-inside-txt">
            <h3>{t('ld_in2_t')}</h3>
            <p>{t('ld_in2_d')}</p>
            <ul className="pl-features ld-inside-list">
              {[1, 2, 3].map(i => (
                <li key={i}><span className="pl-ic on">✔</span>{t(`ld_in2_b${i}`)}</li>
              ))}
            </ul>
          </div>
        </div>

        <div className="ld-sep" />

        {/* ── Como funciona ─────────────────────────────────────── */}
        <h2 className="pl-section-title">{t('ld_how_title')}</h2>
        <div className="ld-how">
          {[
            { n: 1, img: shotPanel,  alt: 'Painel de informações do modelo importado' },
            { n: 2, img: shotApp,    alt: 'Pintando a região de corte no ZefiroSplit' },
            { n: 3, img: shotPanel2, alt: 'Configurações de sensibilidade e raio de expansão' },
          ].map(({ n, img, alt }) => (
            <div className="ld-step ld-step-img" key={n}>
              <div className="ld-step-thumb">
                <img src={img} alt={alt} loading="lazy" />
              </div>
              <div className="ld-step-num">0{n}</div>
              <b>{t(`ld_how${n}_t`)}</b>
              <p>{t(`ld_how${n}_d`)}</p>
            </div>
          ))}
        </div>

        <div className="ld-sep" />

        {/* ── Funcionalidades ───────────────────────────────────── */}
        <h2 className="pl-section-title" id="features">{t('ld_feat_title')}</h2>
        <div className="ld-feat-grid">
          {featCards.map(({ k, ic }) => (
            <div className="ld-feat-card" key={k}>
              <span className="ld-feat-ic">{ic}</span>
              <span>{t(k)}</span>
            </div>
          ))}
        </div>

        {/* ── Planos ───────────────────────────────────────────── */}
        <h2 className="pl-section-title" id="planos">{t('ld_plans_title')}</h2>
        <p className="ld-plans-sub">{t('ld_plans_sub')}</p>
        <div className="pl-cards ld-plans">
          {['essencial', 'pro'].map(id => {
            const p = PLANS[id]
            return (
              <div className={`pl-card ${id}`} key={id} data-testid={`ld-plan-${id}`}>
                {p.popular && <span className="pl-popular">{t('plans_popular')}</span>}
                <div className="pl-card-name">{t(id === 'pro' ? 'plan_pro_name' : 'plan_essencial_name')}</div>
                <div className="pl-card-desc">{t(id === 'pro' ? 'plan_pro_desc' : 'plan_essencial_desc')}</div>
                <div className="pl-price">
                  <span className="pl-amount">{fmtBRL(p.monthly)}</span>
                  <span className="pl-period">{t('plans_per_month')}</span>
                </div>
                <div className="pl-price-sub">
                  {tf('plans_equiv', { v: fmtBRL(p.annualPerMonth) })} ({t('plans_annual').toLowerCase()})
                </div>
                <div className="pl-chip">
                  {t(id === 'pro' ? 'chip_unlimited' : 'chip_25mo')}
                </div>
              </div>
            )
          })}
        </div>

        {/* ── Depoimentos ──────────────────────────────────────── */}
        <h2 className="pl-section-title">{t('ld_testi_title')}</h2>
        <div className="ld-grid3">
          {testimonials.map(([n, d]) => (
            <div className="ld-testi-card" key={n}>
              <div className="ld-stars">★★★★★</div>
              <p className="ld-quote">{t(d)}</p>
              <div className="ld-author-row">
                <div className="ld-author-avatar">{t(n)[0]}</div>
                <b className="ld-author">{t(n)}</b>
              </div>
            </div>
          ))}
        </div>

        <Faq />

        {/* ── CTA banner final ─────────────────────────────────── */}
        <div className="ld-cta-banner">
          <div className="ld-cta-glow" aria-hidden="true" />
          <div className="pl-hero-badge" style={{ display: 'inline-flex', marginBottom: 20 }}>
            ✂️ Comece agora
          </div>
          <h2>{t('ld_hero_title')}</h2>
          <p>{t('ld_hero_sub')}</p>
          <a className="pl-co-pay-btn ld-buy" href="/comprar" data-testid="ld-buy-final"
             onClick={e => { e.preventDefault(); navigate('/comprar') }}>
            {t('ld_cta_buy')}
          </a>
          <div className="pl-cta-sub" style={{ marginTop: 12 }}>{t('ld_cta_sub')}</div>
        </div>

      </div>

      {/* ── Rodapé premium — full-width, fora do pl-wrap ──────── */}
      <footer className="ld-footer">
        <div className="ld-footer-glow" aria-hidden="true" />
        <div className="ld-footer-content">
          <div className="ld-footer-brand">
            <LogoMark size="lg" />
            <p className="ld-footer-tagline">{t('ld_footer_note')}</p>
            <a href="tel:+5561920192600" className="ld-footer-phone-link">
              📱 +55 61 9201-9260
            </a>
          </div>
          <div className="ld-footer-col">
            <span className="ld-footer-col-title">{t('ld_footer_product')}</span>
            <a href="#features">{t('ld_nav_features')}</a>
            <a href="#planos">{t('ld_nav_plans')}</a>
            <a href="/comprar" onClick={e => { e.preventDefault(); navigate('/comprar') }}>{t('ld_cta_buy')}</a>
          </div>
          <div className="ld-footer-col">
            <span className="ld-footer-col-title">{t('ld_footer_support')}</span>
            <a href="#faq">FAQ</a>
            <a href="mailto:suporte@zefirosplit.com">{t('ld_footer_contact')}</a>
            <a href="tel:+5561920192600">📱 +55 61 9201-9260</a>
          </div>
          <div className="ld-footer-col">
            <span className="ld-footer-col-title">{t('ld_footer_legal')}</span>
            <a href="#">{t('ld_footer_terms')}</a>
            <a href="#">{t('ld_footer_privacy')}</a>
          </div>
        </div>
        <div className="ld-footer-bottom-bar">
          <span className="ld-footer-copy">© {new Date().getFullYear()} ZefiroSplit — 3D Mesh Splitter</span>
        </div>
      </footer>

    </div>
  )
}
