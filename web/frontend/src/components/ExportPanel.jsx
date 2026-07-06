import { useState } from 'react'
import { t, tf } from '../i18n.js'
import { useStore } from '../store.js'
import { api } from '../api.js'

// Paleta compartilhada com o Viewer3D — indexada pelo idx da parte no backend
const PART_COLORS = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4', '#ec4899', '#84cc16']

function download(url, filename) {
  const a = document.createElement('a')
  a.href = url
  if (filename) a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

const DONE_COLORS = ['#22c55e', '#16a34a', '#15803d', '#166534', '#14532d']

export default function ExportPanel() {
  const { sessionId, parts, completedNames, exportFmt, warnings, lang } = useStore()
  const setFmt = (f) => useStore.setState({ exportFmt: f })
  const [names, setNames] = useState({})

  if (!sessionId || parts.length === 0) return null

  // No step result, `parts` já é a lista completa do backend (parts_meta),
  // com índices corretos — inclui as partes marcadas como prontas.
  const allParts = parts

  function getName(p) {
    return names[p.idx] ?? p.name ?? `part_${p.idx + 1}`
  }

  function setName(idx, v) {
    setNames(prev => ({ ...prev, [idx]: v }))
  }

  function exportPart(p) {
    const filename = `${getName(p)}.${exportFmt}`
    download(api.exportUrl(sessionId, p.idx, exportFmt, getName(p)), filename)
  }

  function exportZip() {
    const nameMap = {}
    for (const p of allParts) nameMap[p.idx] = getName(p)
    download(api.exportZipUrl(sessionId, exportFmt, nameMap))
  }

  return (
    <div className="panel-section">
      <h3>{t('export_title')}</h3>

      <div className="export-fmt-row">
        {['stl', 'obj'].map(f => (
          <button
            key={f}
            className={`fmt-btn ${exportFmt === f ? 'active' : ''}`}
            onClick={() => setFmt(f)}
          >
            {f.toUpperCase()}
          </button>
        ))}
      </div>

      <div className="export-parts">
        {allParts.map((p, i) => {
          const isDone = completedNames.includes(p.name)
          const color = isDone ? DONE_COLORS[i % DONE_COLORS.length] : PART_COLORS[p.idx % PART_COLORS.length]
          return (
            <div key={p.idx} className="export-part-row">
              <div className="export-part-color" style={{ background: color }} />
              <input
                className="export-name-input"
                value={getName(p)}
                onChange={e => setName(p.idx, e.target.value)}
                spellCheck={false}
              />
              <span className="export-name-ext">.{exportFmt}</span>
              <button
                className="export-dl-btn"
                title={t('export_download')}
                onClick={() => exportPart(p)}
              >
                <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                  <path d="M6.5 1v8M3 6.5l3.5 3.5 3.5-3.5M1 12h11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
            </div>
          )
        })}
      </div>

      <button className="btn-primary" style={{ marginTop: 10 }} onClick={exportZip}>
        {allParts.length > 2 ? tf('export_zip_all', { n: allParts.length }) : t('export_zip')}
      </button>

      {warnings?.length > 0 && (
        <div className="warnings-box" style={{ marginTop: 10 }}>
          {warnings.join(' • ')}
        </div>
      )}
    </div>
  )
}
