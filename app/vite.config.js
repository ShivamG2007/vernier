import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import { safeRecordsMiddleware } from './server/safeRecords.js'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), ['VERNIER_', 'VITE_BACKEND_URL'])
  const records = safeRecordsMiddleware({
    backendUrl: env.VERNIER_BACKEND_URL || env.VITE_BACKEND_URL,
    adminKey: env.VERNIER_ADMIN_KEY,
  })
  return {
    plugins: [
      react(),
      {
        name: 'vernier-safe-records',
        configureServer(server) { server.middlewares.use(records) },
        configurePreviewServer(server) { server.middlewares.use(records) },
      },
    ],
  }
})
