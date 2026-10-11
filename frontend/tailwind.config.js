/** @type {import('tailwindcss').Config} */
// v5 "control room, daylight": lavender-white page, ink text, royal blue signal, rose for attacks.
// Colors are CSS variables (src/index.css) so light and dark themes swap at once.
// Token names kept from v0 (ink = surfaces, fog = text) so every page restyles at once.
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: { 950: 'rgb(var(--ink-950) / <alpha-value>)', 900: 'rgb(var(--ink-900) / <alpha-value>)', 850: 'rgb(var(--ink-850) / <alpha-value>)', 800: 'rgb(var(--ink-800) / <alpha-value>)', 700: 'rgb(var(--ink-700) / <alpha-value>)', 600: 'rgb(var(--ink-600) / <alpha-value>)' },
        fog: { 100: 'rgb(var(--fog-100) / <alpha-value>)', 300: 'rgb(var(--fog-300) / <alpha-value>)', 400: 'rgb(var(--fog-400) / <alpha-value>)', 500: 'rgb(var(--fog-500) / <alpha-value>)' },
        signal: { violet: '#2747E0', cyan: '#4F7BFF' },
        navy: { DEFAULT: '#1B2A8C', soft: '#24369F' },
        rose: { glow: '#E5486B' },
        pill: '#FFFFFF',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        display: ['"Inter Tight"', 'Inter', 'system-ui', 'sans-serif'],
        serif: ['"Instrument Serif"', 'Georgia', 'serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        soft: '0 1px 2px rgba(21,27,46,0.04), 0 12px 32px -8px rgba(39,71,224,0.12)',
        float: '0 18px 50px -12px rgba(21,27,46,0.25)',
        rose: '0 0 0 1px rgba(229,72,107,0.25), 0 10px 30px -6px rgba(229,72,107,0.45)',
        blue: '0 0 0 1px rgba(39,71,224,0.2), 0 10px 30px -6px rgba(39,71,224,0.35)',
      },
    },
  },
  plugins: [],
}
