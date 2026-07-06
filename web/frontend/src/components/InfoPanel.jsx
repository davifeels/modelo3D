import { t } from '../i18n.js'
import { useStore } from '../store.js'

const IconVerts = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <circle cx="2" cy="7" r="1.5" stroke="currentColor" strokeWidth="1.2"/>
    <circle cx="7" cy="2" r="1.5" stroke="currentColor" strokeWidth="1.2"/>
    <circle cx="12" cy="7" r="1.5" stroke="currentColor" strokeWidth="1.2"/>
    <circle cx="7" cy="12" r="1.5" stroke="currentColor" strokeWidth="1.2"/>
    <path d="M3.5 7h3M7 3.5v3M8.5 7h3M7 8.5v3" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity=".5"/>
  </svg>
)

const IconFaces = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M2 11L7 2l5 9H2z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
    <path d="M4 9h6" stroke="currentColor" strokeWidth="1" strokeLinecap="round" opacity=".5"/>
  </svg>
)

const IconDims = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M2 5V2h3M9 2h3v3M2 9v3h3M9 12h3V9" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
    <rect x="4" y="4" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1" opacity=".5"/>
  </svg>
)

const IconVolume = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M7 1.5l5 3v5l-5 3-5-3v-5l5-3z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
    <path d="M7 1.5v11.5M2 4.5l5 3 5-3" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" opacity=".5"/>
  </svg>
)

const IconWatertight = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M7 1.5C7 1.5 2.5 5.5 2.5 8.5a4.5 4.5 0 0 0 9 0C11.5 5.5 7 1.5 7 1.5z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
  </svg>
)

const IconPainted = () => (
  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
    <path d="M2 12c1 0 2.5-.7 2.5-2.5V5l5-3 1.5 1.5-3 5C10 8.5 12 9.5 12 11s-1 2-2 2H2z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round"/>
  </svg>
)

export default function InfoPanel() {
  const { info, paintedCount, lang } = useStore()
  if (!info) return null

  const [dx, dy, dz] = (info.dims || [0, 0, 0]).map(v => v.toFixed(1))
  const total = info.faces || 0
  const pctPainted = total > 0 ? ((paintedCount / total) * 100).toFixed(0) : 0

  return (
    <div className="info-panel">
      <div className="info-section-title">{t('info_title')}</div>

      {info.name && (
        <div className="info-filename-row">
          <span className="info-filename-label">{t('info_filename')}</span>
          <span className="info-filename-val" title={info.name}>{info.name}</span>
        </div>
      )}

      <div className="info-rows-icon">
        <div className="info-row-icon">
          <span className="iri-icon"><IconVerts /></span>
          <span className="iri-label">{t('info_vertices')}</span>
          <span className="iri-value">{(info.vertices || 0).toLocaleString()}</span>
        </div>
        <div className="info-row-icon">
          <span className="iri-icon"><IconFaces /></span>
          <span className="iri-label">{t('info_faces')}</span>
          <span className="iri-value">{(info.faces || 0).toLocaleString()}</span>
        </div>
        <div className="info-row-icon">
          <span className="iri-icon"><IconDims /></span>
          <span className="iri-label">{t('info_dims')}</span>
          <span className="iri-value" style={{ fontSize: 10 }}>{dx} × {dy} × {dz} mm</span>
        </div>
        {info.volume_cm3 != null && (
          <div className="info-row-icon">
            <span className="iri-icon"><IconVolume /></span>
            <span className="iri-label">{t('info_volume')}</span>
            <span className="iri-value">{info.volume_cm3.toLocaleString()} cm³</span>
          </div>
        )}
        <div className="info-row-icon">
          <span className="iri-icon"><IconWatertight /></span>
          <span className="iri-label">{t('info_watertight')}</span>
          <span className={`iri-badge ${info.is_watertight ? 'badge-ok' : 'badge-warn'}`}>
            {info.is_watertight ? t('info_wt_ok') : t('info_wt_open')}
          </span>
        </div>
        <div className="info-row-icon">
          <span className="iri-icon"><IconPainted /></span>
          <span className="iri-label">{t('info_painted')}</span>
          <span className="iri-value">{paintedCount.toLocaleString()} ({pctPainted}%)</span>
        </div>
      </div>
    </div>
  )
}
