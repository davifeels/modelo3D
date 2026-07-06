import { useRef, useState } from 'react'
import { t, tf } from '../i18n.js'
import { useStore } from '../store.js'
import { api } from '../api.js'

function UploadIcon() {
  return (
    <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="8" y="32" width="32" height="4" rx="2" fill="#7c3aed" opacity=".3"/>
      <rect x="8" y="38" width="32" height="2" rx="1" fill="#7c3aed" opacity=".15"/>
      <path d="M24 28V12" stroke="#7c3aed" strokeWidth="2.5" strokeLinecap="round"/>
      <path d="M16 20L24 12L32 20" stroke="#7c3aed" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
      <rect x="4" y="10" width="40" height="30" rx="4" stroke="#7c3aed" strokeWidth="1.5" opacity=".2"/>
    </svg>
  )
}

// Fluxo de upload compartilhado (DropZone e botão "Abrir arquivo" do header)
export async function uploadModelFile(file) {
  if (!file) return
  const { setLoading, afterUpload, setError } = useStore.getState()
  const ext = file.name.split('.').pop().toLowerCase()
  if (!['stl', 'obj'].includes(ext)) {
    setError(t('err_format'))
    return
  }
  setLoading(true, t('upload_reading'), 10)
  try {
    setLoading(true, t('upload_parsing'), 40)
    const data = await api.upload(file)
    setLoading(true, t('upload_done'), 90)
    afterUpload(data.session_id, data.info, data.parts)
    if (data.info?.scaled_from) {
      const unitLabels = { m: t('unit_m'), cm: t('unit_cm'), 'µm': t('unit_um') }
      const from = unitLabels[data.info.scaled_from] || data.info.scaled_from
      const dims = data.info.dims
      setError(`${tf('warn_scaled', { unit: from })}\n${t('dims_label')}: ${dims[0].toFixed(0)} × ${dims[1].toFixed(0)} × ${dims[2].toFixed(0)} mm`)
    }
  } catch (e) {
    setError(e.message || t('err_upload'))
  } finally {
    setLoading(false)
  }
}

export default function DropZone() {
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef()
  const { lang } = useStore()

  const handleFile = uploadModelFile

  function onDrop(e) {
    e.preventDefault()
    setDragOver(false)
    handleFile(e.dataTransfer.files[0])
  }

  return (
    <div
      className={`dropzone ${dragOver ? 'drag-over' : ''}`}
      onDragOver={e => { e.preventDefault(); setDragOver(true) }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
      onClick={() => inputRef.current.click()}
    >
      <div className={`dropzone-box ${dragOver ? 'drag-over' : ''}`}>
        <div className="dropzone-icon"><UploadIcon /></div>
        <div className="dropzone-title">
          {dragOver ? t('drop_drag_over') : t('drop_title')}
        </div>
        <div className="dropzone-sub">{t('drop_or')}</div>
        <button
          className="btn-primary"
          style={{ width: 'auto', padding: '9px 28px' }}
          onClick={e => { e.stopPropagation(); inputRef.current.click() }}
        >
          {t('drop_btn')}
        </button>
        <div className="dropzone-formats">{t('drop_formats')}</div>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".stl,.obj,.STL,.OBJ"
        style={{ display: 'none' }}
        onChange={e => handleFile(e.target.files[0])}
      />
    </div>
  )
}
