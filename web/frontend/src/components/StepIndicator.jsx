import { Fragment } from 'react'
import { t } from '../i18n.js'
import { useStore } from '../store.js'

const STEPS = ['step_import', 'step_cut', 'step_paint', 'step_preview', 'step_process', 'step_export']

const STEP_MAP = {
  idle: 0,
  loaded: 1,
  cutting: 1,
  painting: 2,
  previewing: 3,
  processing: 4,
  result: 5,
}

export default function StepIndicator() {
  const step = useStore(s => s.step)
  const lang = useStore(s => s.lang)
  const current = STEP_MAP[step] ?? 0

  return (
    <div className="step-indicator">
      {STEPS.map((key, i) => (
        <Fragment key={i}>
          <div className={`step-item${i < current ? ' done' : i === current ? ' active' : ''}`}>
            <div className="step-num">
              {i < current ? '✓' : i + 1}
            </div>
            <span className="step-label">{t(key)}</span>
          </div>
          {i < STEPS.length - 1 && (
            <div className={`step-connector${i < current ? ' done' : ''}`} />
          )}
        </Fragment>
      ))}
    </div>
  )
}
