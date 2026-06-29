import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Standalone dashboard app served at the ROOT of its own subdomain
// (app.stampn.net) — so routes are bare (/login, /cards). The marketing app
// lives at stampn.net and links to app.stampn.net on "Login".
// Port 5174 to avoid clashing with the marketing app in local dev.
export default defineConfig({
  plugins: [react()],
  server: { port: 5174 },
})
