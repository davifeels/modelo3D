import '../styles/logo.css'

// size: 'sm' | 'md' | 'lg' | 'xl'
export default function LogoMark({ size = 'md', className = '' }) {
  return (
    <span className={`logo-mark lm-${size} ${className}`}>
      ZefiroSplit
    </span>
  )
}
