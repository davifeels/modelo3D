import { useEffect, useState } from 'react'

// Mini-roteador por pathname — o nginx e o Vite dev server já fazem fallback
// de SPA para /index.html, então /planos e /checkout funcionam sem config extra.

export function navigate(path) {
  window.history.pushState({}, '', path)
  window.dispatchEvent(new PopStateEvent('popstate'))
}

export function usePathRoute() {
  const [path, setPath] = useState(window.location.pathname)
  useEffect(() => {
    const onPop = () => setPath(window.location.pathname)
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])
  return path
}

// Lê os query params atuais (?plano=pro&periodo=anual)
export function getQuery() {
  return new URLSearchParams(window.location.search)
}
