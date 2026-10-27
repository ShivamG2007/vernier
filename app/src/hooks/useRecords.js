import { useEffect, useState } from 'react'

const refreshDelay = 5000

export function useRecords(table, day = '', enabled = true) {
  const [state, setState] = useState({ data: [], phase: 'loading', updatedAt: null, error: null })

  useEffect(() => {
    if (!enabled) return
    setState({ data: [], phase: 'loading', updatedAt: null, error: null })
    let active = true
    let timer
    let controller

    async function refresh() {
      controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 5000)
      try {
        const query = table === 'bookings' && day ? `?day=${encodeURIComponent(day)}` : ''
        const response = await fetch(`/api/records/${table}${query}`, { signal: controller.signal, cache: 'no-store' })
        if (!response.ok) throw new Error(`Request failed (${response.status})`)
        const data = await response.json()
        if (!Array.isArray(data)) throw new Error('Unexpected response')
        if (active) setState({ data, phase: 'ready', updatedAt: Date.now(), error: null })
      } catch (error) {
        if (active) setState((previous) => ({ ...previous, phase: 'error', error: error.name === 'AbortError' ? 'Request timed out' : 'Updates unavailable' }))
      } finally {
        clearTimeout(timeout)
        if (active) timer = setTimeout(refresh, refreshDelay)
      }
    }

    refresh()
    return () => {
      active = false
      clearTimeout(timer)
      controller?.abort()
    }
  }, [table, day, enabled])

  return state
}
