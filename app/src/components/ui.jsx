import { useLayoutEffect, useRef, useState } from 'react'

export function Brand({ href, className = '' }) {
  const content = <><span className="sr-only">Vernier</span><span className="brand-visible" aria-hidden="true"><span className="brand-wordmark"><img className="brand-mark" src="/vernier-mark.png" alt="" />ERNIER</span></span></>
  return href ? <a className={`brand ${className}`} href={href}>{content}</a> : <div className={`brand ${className}`}>{content}</div>
}

export function Icon({ name, size = 20 }) {
  const paths = {
    home: <><path d="m3 10 9-7 9 7v10H3V10Z" /><path d="M9 21v-7h6v7" /></>,
    search: <><circle cx="10.8" cy="10.8" r="7" /><path d="m16 16 5 5" /></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M7 3v4m10-4v4M3 10h18" /></>,
    bag: <><path d="M4 8h16l-1 13H5L4 8Z" /><path d="M9 9V6a3 3 0 0 1 6 0v3" /></>,
    washer: <><rect x="3" y="2" width="18" height="20" rx="2" /><path d="M3 7h18" /><circle cx="7" cy="4.5" r=".5" /><circle cx="10" cy="4.5" r=".5" /><circle cx="12" cy="14.5" r="5" /><path d="M9 14.5c1.5-1.2 3.5 1.2 6 0" /></>,
    campus: <><path d="m3 9 9-6 9 6v12H3V9Z" /><path d="M8 21v-9h8v9M3 10h18" /></>,
    user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
    chevron: <path d="m6 9 6 6 6-6" />,
    arrow: <><path d="M4 12h16m-6-6 6 6-6 6" /></>,
    info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5m0-8h.01" /></>,
    wifi: <><path d="M3 9a14 14 0 0 1 18 0M6 12a9 9 0 0 1 12 0m-9 3a5 5 0 0 1 6 0" /><circle cx="12" cy="19" r=".7" fill="currentColor" /></>,
  }
  return <svg aria-hidden="true" viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">{paths[name] || paths.info}</svg>
}

export function SearchField({ value, onChange, label, placeholder }) {
  return <label className="search-field"><Icon name="search" size={17} /><span className="sr-only">{label}</span><input type="search" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} /></label>
}

export function FilterTabs({ label, options, value, onChange }) {
  const row = useRef(null)
  const [indicator, setIndicator] = useState(null)
  useLayoutEffect(() => {
    const element = row.current
    if (!element) return
    const measure = () => {
      const active = [...element.querySelectorAll('button')].find((button) => button.dataset.value === value)
      if (active) setIndicator({ left: active.offsetLeft, width: active.offsetWidth })
    }
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [options, value])
  const onKeyDown = (event, index) => {
    const move = { ArrowRight: index + 1, ArrowLeft: index - 1, Home: 0, End: options.length - 1 }[event.key]
    if (move === undefined) return
    event.preventDefault()
    const next = (move + options.length) % options.length
    onChange(options[next])
    row.current?.querySelectorAll('button')[next]?.focus()
  }
  return <div className="filter-tabs" ref={row} role="group" aria-label={label}>
    {options.map((option, index) => <button key={option} data-value={option} type="button" aria-pressed={value === option} className={value === option ? 'is-selected' : ''} onClick={() => onChange(option)} onKeyDown={(event) => onKeyDown(event, index)}>{option}</button>)}
    {indicator && <span className="filter-indicator" aria-hidden="true" style={{ width: indicator.width, transform: `translateX(${indicator.left}px)` }} />}
  </div>
}

export function LoadingState() {
  return <div className="state" role="status"><div className="skeleton wide" /><div className="skeleton" /><div className="skeleton short" /><span className="sr-only">Loading records</span></div>
}

export function EmptyState({ title = 'Nothing here yet', description }) {
  return <div className="state"><h3>{title}</h3>{description && <p>{description}</p>}</div>
}

export function ConnectionError({ offline = false, stale = false }) {
  return <div className="state state--error" role="alert"><Icon name="wifi" size={19} /><div><h3>{offline ? 'You’re offline' : 'Couldn’t load updates'}</h3><p>{stale ? 'Showing the last records we received.' : 'Check the connection and try again.'}</p></div></div>
}
