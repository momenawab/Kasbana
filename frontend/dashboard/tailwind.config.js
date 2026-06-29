/** @type {import('tailwindcss').Config} */
// Direction C — "Bold Modern" tokens (from main/docs/mockups/dashboard/direction-c.html).
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        ink: { DEFAULT: '#0E1B2A', 2: '#16293D', 3: '#26405A' },
        amber: { DEFAULT: '#E0A23B', d: '#C6862A', bg: '#FBF1DD' },
        clay: { DEFAULT: '#C75D43', bg: '#FAE7E0' },
        teal: { DEFAULT: '#1C7C73', bg: '#DFF0ED' },
        paper: '#FBF8F3',
        line: '#E7E1D6',
        tx: { DEFAULT: '#1F2933', 2: '#566069', 3: '#8A949C' },
        success: '#1C7C73',
        warn: '#C6862A',
        danger: '#C0392B',
      },
      fontFamily: {
        head: ['"Space Grotesk"', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
        ar: ['Cairo', 'Tajawal', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      borderRadius: { card: '16px', ctl: '10px' },
      boxShadow: { bold: '0 12px 32px -10px rgba(14,27,42,.30)' },
    },
  },
  plugins: [],
}
