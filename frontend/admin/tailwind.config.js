/** @type {import('tailwindcss').Config} */
// Platform admin console — a dark, dense, professional back-office palette
// (distinct from the merchant dashboard's warm Direction-C theme).
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Slate surfaces
        bg: '#0B1220', // app background
        surface: { DEFAULT: '#131C2B', 2: '#1B2637', 3: '#26344A' },
        line: '#2A3648',
        // Brand accent (Stampn amber) + status
        brand: { DEFAULT: '#E0A23B', d: '#C6862A', bg: '#2A2313' },
        tx: { DEFAULT: '#E6EAF0', 2: '#9AA7B8', 3: '#6B7A8D' },
        success: '#2FBF87',
        warn: '#E0A23B',
        danger: '#E5533B',
        info: '#3B9FE0',
      },
      fontFamily: {
        head: ['"Space Grotesk"', 'system-ui', 'sans-serif'],
        body: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      borderRadius: { card: '14px', ctl: '9px' },
      boxShadow: { card: '0 8px 24px -12px rgba(0,0,0,.5)' },
    },
  },
  plugins: [],
}
