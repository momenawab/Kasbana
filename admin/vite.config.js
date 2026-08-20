import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// Standalone platform admin console served at the root of admin.stampn.net.
// Port 5175 to avoid clashing with the marketing (5173) and dashboard (5174)
// apps in local dev.
//
// PWA (installable + shell cache): admins can add the console to their phone's
// home screen and open it full-screen. The app shell is precached; API calls
// still need a connection (no offline queue). The SW is disabled in dev.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['apple-touch-icon.png', 'logo.png'],
      devOptions: { enabled: false },
      workbox: {
        cleanupOutdatedCaches: true,
        clientsClaim: true,
        skipWaiting: true,
        navigateFallback: 'index.html',
        // Never let the SPA fallback swallow admin API calls.
        navigateFallbackDenylist: [/^\/api/],
        globPatterns: ['**/*.{js,css,html,svg,png,woff2}'],
      },
      manifest: {
        name: 'Stampn Admin Console',
        short_name: 'Stampn Admin',
        description: 'Stampn platform operations console.',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        orientation: 'portrait',
        background_color: '#0F0D18',
        theme_color: '#0F0D18',
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
  server: { port: 5175 },
})
