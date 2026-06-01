/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0A0A0B',
        sidebar: '#0B0B0D',
        card: '#131417',
        cardhi: '#181A1E',
        border: '#212228',
        soft: '#1A1B20',
        txt: '#ECEDEE',
        muted: '#8B8D96',
        faint: '#62646D',
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
