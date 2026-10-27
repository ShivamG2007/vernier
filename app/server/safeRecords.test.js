import test from 'node:test'
import assert from 'node:assert/strict'
import { publicRecord, safeRecordsMiddleware } from './safeRecords.js'

function request(path, middleware, method = 'GET') {
  return new Promise((resolve) => {
    const res = {
      writeHead(status, headers) { this.status = status; this.headers = headers; return this },
      end(body) { resolve({ status: this.status, headers: this.headers, body: JSON.parse(body) }) },
    }
    middleware({ url: path, method }, res, () => resolve({ next: true }))
  })
}

test('maps new item and machine fields while dropping sensitive values', () => {
  const item = publicRecord('lost_found', {
    id: 3, kind: 'found', name: 'bottle', color: 'blue', place: 'Library',
    status: 'unclaimed', dateTime: '2026-10-28T10:00:00+00:00',
    reporter: 'student@c.us', pleaseConsultThisPerson: 'private', source: 'camera',
  })
  assert.equal(item.item, 'bottle')
  assert.equal(item.created, '2026-10-28T10:00:00+00:00')
  assert.equal(item.cameraObservation, true)
  assert.equal(item.reporter, undefined)
  assert.equal(item.pleaseConsultThisPerson, undefined)
  assert.equal(publicRecord('machines', { id: 'm1', updated_at: 'now' }).updated, 'now')
  const listing = publicRecord('listings', { id: 4, item: 'Call 9876543210', price: '₹100' })
  assert.equal(listing.item.includes('9876543210'), false)
})

test('uses wrapped public routes and removes private listing fields', async (t) => {
  const original = globalThis.fetch
  t.after(() => { globalThis.fetch = original })
  globalThis.fetch = async (url, options) => {
    assert.equal(url.pathname, '/listings')
    assert.equal(options.headers['X-Vernier-Key'], 'server-only')
    return { ok: true, status: 200, json: async () => ({ listings: [{ id: 2, kind: 'sell', item: 'Book', price: '₹100', contact: 'private@c.us', details: 'Call 9999999999' }] }) }
  }
  const result = await request('/api/records/listings', safeRecordsMiddleware({ backendUrl: 'http://localhost:8000', adminKey: 'server-only' }))
  assert.equal(result.status, 200)
  assert.deepEqual(result.body, [{ id: 2, kind: 'sell', item: 'Book', price: '₹100', status: null, created: null }])
  assert.equal(JSON.stringify(result.body).includes('private'), false)
})

test('does not turn malformed responses into empty success', async (t) => {
  const original = globalThis.fetch
  t.after(() => { globalThis.fetch = original })
  globalThis.fetch = async () => ({ ok: true, status: 200, json: async () => ({ events: {} }) })
  const result = await request('/api/records/events', safeRecordsMiddleware({ backendUrl: 'http://localhost:8000' }))
  assert.equal(result.status, 502)
})

test('forwards booking day and keeps only that day', async (t) => {
  const original = globalThis.fetch
  t.after(() => { globalThis.fetch = original })
  globalThis.fetch = async (url) => {
    assert.equal(url.searchParams.get('day'), '2026-10-28')
    return { ok: true, status: 200, json: async () => ({ bookings: [
      { id: 1, room: 'A', day: '2026-10-28', start: '10:00', end: '11:00', booked_by: 'private' },
      { id: 2, room: 'B', day: '2026-10-29', start: '10:00', end: '11:00' },
    ] }) }
  }
  const result = await request('/api/records/bookings?day=2026-10-28', safeRecordsMiddleware({ backendUrl: 'http://localhost:8000' }))
  assert.equal(result.status, 200)
  assert.equal(result.body.length, 1)
  assert.equal(result.body[0].booked_by, undefined)
})

test('keeps the older records API as a read-only fallback', async (t) => {
  const original = globalThis.fetch
  t.after(() => { globalThis.fetch = original })
  let calls = 0
  globalThis.fetch = async (url) => {
    calls++
    if (calls === 1) {
      assert.equal(url.pathname, '/items')
      return { ok: false, status: 404 }
    }
    if (calls === 2) {
      assert.equal(url.pathname, '/health')
      return { ok: true, status: 200, json: async () => ({ backend: 'ok', ollama_url: 'http://localhost:11434' }) }
    }
    assert.equal(url.pathname, '/records/lost_found')
    return { ok: true, status: 200, json: async () => [{ id: 9, kind: 'lost', item: 'Bag', colour: 'black', status: 'open', created: '2026-10-28', contact: 'private' }] }
  }
  const result = await request('/api/records/lost_found', safeRecordsMiddleware({ backendUrl: 'http://localhost:8000' }))
  assert.equal(result.status, 200)
  assert.equal(result.body[0].item, 'Bag')
  assert.equal(result.body[0].contact, undefined)
})

test('uses complete open-lost and unclaimed-found routes with safe fields', async (t) => {
  const original = globalThis.fetch
  t.after(() => { globalThis.fetch = original })
  globalThis.fetch = async (url) => {
    assert.ok(['/items/lost', '/items/unclaimed'].includes(url.pathname))
    const found = url.pathname.endsWith('unclaimed')
    return { ok: true, status: 200, json: async () => ({ items: [{
      id: found ? 2 : 1, kind: found ? 'found' : 'lost', item: 'Notebook',
      status: found ? 'unclaimed' : 'open', reporter: 'private@c.us',
    }] }) }
  }
  const middleware = safeRecordsMiddleware({ backendUrl: 'http://localhost:8000' })
  for (const route of ['open_lost', 'unclaimed_found']) {
    const result = await request(`/api/records/${route}`, middleware)
    assert.equal(result.status, 200)
    assert.equal(result.body.length, 1)
    assert.equal(result.body[0].reporter, undefined)
  }
})

test('filters the older backend response for a dedicated item view', async (t) => {
  const original = globalThis.fetch
  t.after(() => { globalThis.fetch = original })
  globalThis.fetch = async (url) => url.pathname === '/items/lost'
    ? { ok: false, status: 404 }
    : url.pathname === '/health'
      ? { ok: true, status: 200, json: async () => ({ backend: 'ok', ollama_url: 'http://localhost:11434' }) }
      : { ok: true, status: 200, json: async () => [
      { id: 1, kind: 'lost', item: 'Book', status: 'open' },
      { id: 2, kind: 'found', item: 'Book', status: 'open' },
      { id: 3, kind: 'lost', item: 'Bag', status: 'claimed' },
    ] }
  const result = await request('/api/records/open_lost', safeRecordsMiddleware({ backendUrl: 'http://localhost:8000' }))
  assert.equal(result.status, 200)
  assert.deepEqual(result.body.map((row) => row.id), [1])
})

test('does not use privileged raw records after a current-backend 404', async (t) => {
  const original = globalThis.fetch
  t.after(() => { globalThis.fetch = original })
  const paths = []
  globalThis.fetch = async (url) => {
    paths.push(url.pathname)
    return url.pathname === '/health'
      ? { ok: true, status: 200, json: async () => ({ backend: 'ok', groups_enabled: false }) }
      : { ok: false, status: 404 }
  }
  const result = await request('/api/records/events', safeRecordsMiddleware({ backendUrl: 'http://localhost:8000', adminKey: 'server-only' }))
  assert.equal(result.status, 502)
  assert.deepEqual(paths, ['/events', '/health'])
})

test('rejects write methods without contacting the backend', async () => {
  const result = await request('/api/records/items', safeRecordsMiddleware({ backendUrl: 'http://localhost:8000' }), 'POST')
  assert.equal(result.status, 404)
  const events = await request('/api/records/events', safeRecordsMiddleware({ backendUrl: 'http://localhost:8000' }), 'POST')
  assert.equal(events.status, 405)
})
