import { createServer } from 'node:http'
import { readFile, stat } from 'node:fs/promises'
import { extname, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { safeRecordsMiddleware } from './safeRecords.js'

const dist = resolve(fileURLToPath(new URL('../dist/', import.meta.url)))
const port = Number(process.env.PORT || 4173)
const host = process.env.HOST || '127.0.0.1'
const records = safeRecordsMiddleware({
  backendUrl: process.env.VERNIER_BACKEND_URL || process.env.VITE_BACKEND_URL,
  adminKey: process.env.VERNIER_ADMIN_KEY,
})
const mime = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon', '.woff2': 'font/woff2',
}

createServer((req, res) => records(req, res, async () => {
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    res.writeHead(405).end()
    return
  }
  let pathname
  try { pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname) } catch {
    res.writeHead(400).end()
    return
  }
  const path = resolve(dist, `.${pathname}`)
  if (path !== dist && !path.startsWith(`${dist}${sep}`)) {
    res.writeHead(404).end()
    return
  }
  try {
    let file = path
    if (!(await stat(file)).isFile()) file = resolve(dist, 'index.html')
    const body = await readFile(file)
    res.writeHead(200, {
      'Content-Type': mime[extname(file)] || 'application/octet-stream',
      'Cache-Control': file.endsWith('index.html') ? 'no-cache' : 'public, max-age=3600',
    })
    res.end(req.method === 'HEAD' ? undefined : body)
  } catch {
    // Unknown client routes still use the single-page entry point.
    try {
      const body = await readFile(resolve(dist, 'index.html'))
      res.writeHead(200, { 'Content-Type': mime['.html'], 'Cache-Control': 'no-cache' })
      res.end(req.method === 'HEAD' ? undefined : body)
    } catch { res.writeHead(503).end('Build the app before starting the server') }
  }
})).listen(port, host, () => console.log(`Vernier app listening at http://${host}:${port}`))
