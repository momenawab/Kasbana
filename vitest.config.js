import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// Unit/component tests (Vitest + Testing Library) for the marketing site.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/test/setup.js',
    include: ['src/**/*.{test,spec}.{js,jsx}'],
  },
})
