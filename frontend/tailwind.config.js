/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        'void': '#0a0a0f',
        'abyss': '#12121a',
        'shadow': '#1a1a26',
        'mist': '#2a2a3d',
        'ash': '#6b6b8a',
        'bone': '#c8c8d4',
        'crimson': '#8b1a1a',
        'gold': '#c9a84c',
      },
      fontFamily: {
        serif: ['Georgia', 'serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
}
