import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Standalone platform admin console served at the root of admin.stampn.net.
// Port 5175 to avoid clashing with the marketing (5173) and dashboard (5174)
// apps in local dev.
export default defineConfig({
  plugins: [react()],
  server: { port: 5175 },
})
