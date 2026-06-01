/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: 'var(--color-bg)',
        sidebar: 'var(--color-sidebar)',
        card: 'var(--color-card)',
        cardhi: 'var(--color-cardhi)',
        border: 'var(--color-border)',
        soft: 'var(--color-soft)',
        txt: 'var(--color-txt)',
        muted: 'var(--color-muted)',
        faint: 'var(--color-faint)',
        blue: '#3B82F6',
        bluehi: '#60A5FA',
        danger: '#F04359',
        good: '#34D399',
        warn: '#FBBF24',
      },
      fontFamily: {
        sans: ['Geist', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"Geist Mono"', '"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      borderRadius: { xl: '14px' },
    },
  },
  plugins: [],
}
