/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        void: '#0A0E12',
        panel: '#121821',
        raised: '#1A2230',
        hair: '#232C3A',
        txt: '#E6EDF3',
        muted: '#8A97A6',
        calm: '#2DD4BF',
        watch: '#FBBF24',
        alert: '#F43F5E',
        signal: '#38BDF8',
      },
      fontFamily: {
        display: ['Michroma', 'ui-sans-serif', 'sans-serif'],
        sans: ['"IBM Plex Sans"', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        panel: '0 1px 0 0 rgba(255,255,255,0.03), 0 10px 30px -16px rgba(0,0,0,0.7)',
        glow: '0 0 0 1px rgba(56,189,248,0.4), 0 0 22px -4px rgba(56,189,248,0.5)',
      },
      keyframes: {
        pulsering: {
          '0%': { boxShadow: '0 0 0 0 rgba(244,63,94,0.55)' },
          '70%': { boxShadow: '0 0 0 12px rgba(244,63,94,0)' },
          '100%': { boxShadow: '0 0 0 0 rgba(244,63,94,0)' },
        },
      },
      animation: { pulsering: 'pulsering 2s ease-out infinite' },
    },
  },
  plugins: [],
}
