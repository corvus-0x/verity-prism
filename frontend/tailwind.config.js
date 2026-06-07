export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['Syne', 'sans-serif'],
        body: ['Outfit', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        // Precision navy palette — remaps all existing slate-* references
        // Higher number = darker, consistent with Tailwind convention
        slate: {
          950: '#020509',
          900: '#040810',
          800: '#0C1424',
          700: '#111E30',
          600: '#1A2A3F',
          500: '#243650',
          400: '#5C7A9B',
          300: '#8BA8C4',
          200: '#BAD0E8',
          100: '#E4F0FC',
          50:  '#F4FAFF',
        },
        // Signal red — primary interactive accent
        crimson: {
          900: '#3B0A0A',
          800: '#5C1010',
          700: '#841616',
          600: '#991B1B',
          500: '#B91C1C',
          400: '#DC2626',
          300: '#EF4444',
          200: '#FCA5A5',
          100: '#FEE2E2',
          50:  '#FFF5F5',
        },
        // Keep surface alias for any direct references
        surface: {
          900: '#040810',
          800: '#0C1424',
          700: '#111E30',
          600: '#1A2A3F',
        },
      },
    },
  },
  plugins: [],
}
