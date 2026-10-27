// Field-limited adapter for the implemented Vernier read APIs.
// The backend address and optional admin key stay on this app server.
const collections = {
  lost_found: { path: 'items', key: 'items' },
  open_lost: { path: 'items/lost', key: 'items', legacy: 'lost_found' },
  unclaimed_found: { path: 'items/unclaimed', key: 'items', legacy: 'lost_found' },
  events: { path: 'events', key: 'events' },
  listings: { path: 'listings', key: 'listings' },
  machines: { path: 'machines', key: 'machines' },
  bookings: { path: 'bookings', key: 'bookings' },
}

const allowed = {
  lost_found: ['id', 'kind', 'item', 'colour', 'place', 'status', 'created', 'cameraObservation'],
  events: ['id', 'title', 'category', 'date', 'venue', 'major', 'created'],
  listings: ['id', 'kind', 'item', 'price', 'status', 'created'],
  machines: ['id', 'location', 'status', 'updated'],
  bookings: ['id', 'room', 'day', 'start', 'end', 'status'],
}

function cleanText(value, max = 160) {
  if (typeof value !== 'string') return null
  return value.slice(0, max)
    .replace(/\+?\d[\d\s().-]{7,}\d/g, (match) => match.replace(/\D/g, '').length >= 10 ? '[contact removed]' : match)
    .replace(/[\w.+-]+@[\w.-]+\.[a-z]{2,}/gi, '[contact removed]')
    .replace(/\b[\w.-]+@(?:c\.us|lid)\b/gi, '[contact removed]')
}

export function publicRecord(table, row) {
  if (!row || typeof row !== 'object' || Array.isArray(row)) return null
  if (typeof row.id !== 'string' && typeof row.id !== 'number') return null
  const publicTable = table === 'open_lost' || table === 'unclaimed_found' ? 'lost_found' : table
  const mapped = publicTable === 'lost_found' ? {
    id: row.id, kind: row.kind, item: row.item ?? row.name,
    colour: row.colour ?? row.color, place: row.place,
    status: row.status, created: row.created ?? row.created_at ?? row.dateTime,
    cameraObservation: row.cameraObservation === true || row.source === 'camera',
  } : table === 'machines' ? {
    id: row.id, location: row.location, status: row.status, updated: row.updated ?? row.updated_at,
  } : { ...row, created: row.created ?? row.created_at }
  return Object.fromEntries(allowed[publicTable].map((field) => {
    const value = mapped[field]
    if (field === 'cameraObservation') return [field, value === true]
    if (field === 'major') return [field, value === true || value === 1]
    if (field === 'id') return [field, typeof value === 'string' || typeof value === 'number' ? value : null]
    return [field, cleanText(value, field === 'date' ? 100 : 160)]
  }))
}

function send(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' })
  res.end(JSON.stringify(body))
}

export function safeRecordsMiddleware({ backendUrl, adminKey = '' } = {}) {
  return async (req, res, next) => {
    const path = req.url?.split('?')[0]
    if (!path?.startsWith('/api/records/')) return next()
    const table = path.slice('/api/records/'.length)
    const collection = collections[table]
    if (!collection) return send(res, 404, { error: 'Unknown collection' })
    if (req.method !== 'GET' && req.method !== 'HEAD') return send(res, 405, { error: 'Method not allowed' })
    if (!backendUrl) return send(res, 503, { error: 'Backend URL is not configured' })
    let day = null
    try { if (table === 'bookings') day = new URL(req.url, 'http://localhost').searchParams.get('day') }
    catch { return send(res, 400, { error: 'Invalid request' }) }
    if (day && !/^\d{4}-\d{2}-\d{2}$/.test(day)) return send(res, 400, { error: 'Invalid booking day' })
    let target
    try {
      const base = new URL(backendUrl)
      if (!['http:', 'https:'].includes(base.protocol)) throw new Error('Invalid protocol')
      target = new URL(collection.path, `${base.href.replace(/\/$/, '')}/`)
      if (day) target.searchParams.set('day', day)
    } catch {
      return send(res, 503, { error: 'Backend URL is invalid' })
    }
    try {
      const headers = { Accept: 'application/json' }
      if (adminKey) headers['X-Vernier-Key'] = adminKey
      let response = await fetch(target, { signal: AbortSignal.timeout(4500), headers })
      let rows
      if (response.status === 404) {
        // A missing current route is an error. Only the older FastAPI service
        // identifies itself with ollama_url in /health and returns bare arrays.
        const health = new URL('health', `${new URL(backendUrl).href.replace(/\/$/, '')}/`)
        const check = await fetch(health, { signal: AbortSignal.timeout(4500), headers })
        const identity = check.ok ? await check.json() : null
        if (identity?.backend !== 'ok' || typeof identity.ollama_url !== 'string' || 'groups_enabled' in identity) {
          return send(res, 502, { error: 'Backend route is unavailable' })
        }
        const legacy = new URL(`records/${collection.legacy || table}`, `${new URL(backendUrl).href.replace(/\/$/, '')}/`)
        response = await fetch(legacy, { signal: AbortSignal.timeout(4500), headers })
        if (response.ok) rows = await response.json()
      } else if (response.ok) {
        const payload = await response.json()
        rows = payload?.[collection.key]
      }
      if (!response.ok) return send(res, 502, { error: 'Backend request failed' })
      if (!Array.isArray(rows)) return send(res, 502, { error: 'Unexpected backend response' })
      const safe = rows.map((row) => publicRecord(table, row))
      if (safe.some((row) => row === null)) return send(res, 502, { error: 'Unexpected backend response' })
      const visible = table === 'open_lost' ? safe.filter((row) => row.kind === 'lost' && row.status === 'open')
        : table === 'unclaimed_found' ? safe.filter((row) => row.kind === 'found' && ['unclaimed', 'open'].includes(row.status))
          : day ? safe.filter((row) => row.day === day) : safe
      return send(res, 200, visible)
    } catch (error) {
      return send(res, error?.name === 'TimeoutError' ? 504 : 502, { error: 'Backend unavailable' })
    }
  }
}
