import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// Standalone dashboard app served at the ROOT of its own subdomain
// (app.stampn.net) — so routes are bare (/login, /cards). The marketing app
// lives at stampn.net and links to app.stampn.net on "Login".
// Port 5174 to avoid clashing with the marketing app in local dev.
//
// PWA (installable + shell cache): merchants/cashiers can add the dashboard to
// their home screen and it opens fast/offline (the app shell is precached; API
// calls still need a connection — no offline queue). The SW is disabled in dev
// so it never fights the MSW mock worker.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'apple-touch-icon.png'],
      devOptions: { enabled: false },
      workbox: {
        cleanupOutdatedCaches: true,
        clientsClaim: true,
        skipWaiting: true,
        navigateFallback: 'index.html',
        // Never let the SPA fallback swallow API or wallet backend calls.
        navigateFallbackDenylist: [/^\/api/, /^\/media/],
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
        // MapLibre GL (~2.5 MB, Locations map) is lazy-loaded and network-only —
        // keep it out of the precache so it doesn't bloat first paint / the SW.
        globIgnores: ['**/maplibre-*.js', '**/maplibre-*.css'],
      },
      manifest: {
        name: 'Stampn — لوحة التحكم',
        short_name: 'Stampn',
        description: 'Stampn merchant dashboard — cards, customers, scan & rewards.',
        lang: 'ar',
        dir: 'rtl',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait',
        background_color: '#1E1B2E',
        theme_color: '#1E1B2E',
        icons: [
          { src: '/pwa-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/pwa-512.png', sizes: '512x512', type: 'image/png' },
          {
            src: '/pwa-maskable-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
    }),
  ],
  server: { port: 5174 },
  build: {
    rollupOptions: {
      output: {
        // Isolate the map stack into a predictable, on-demand chunk so it stays
        // out of the main bundle (and the precache — see globIgnores above).
        manualChunks(id) {
          if (id.includes('@maptiler') || id.includes('maplibre-gl')) return 'maplibre'
        },
      },
    },
  },
})
