/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
      },
      colors: {
        fire: {
          50: '#fff7ed',
          100: '#ffedd5',
          200: '#fed7aa',
          400: '#fb923c',
          500: '#f97316',
          600: '#ea580c',
          700: '#c2410c',
          900: '#7c2d12',
        },
        surface: {
          page: '#f6f7fb',
          card: '#ffffff',
          muted: '#eef1f6',
          border: '#e2e8f0',
        },
      },
      boxShadow: {
        soft: '0 1px 3px rgba(15, 23, 42, 0.06), 0 4px 12px rgba(15, 23, 42, 0.04)',
        panel: '0 8px 32px rgba(15, 23, 42, 0.12)',
        fab: '0 4px 20px rgba(234, 88, 12, 0.35)',
        guia: '0 6px 28px rgba(124, 58, 237, 0.45)',
      },
      animation: {
        'mascote-float': 'mascote-float 3s ease-in-out infinite',
        'guia-pulse': 'guia-pulse 2s ease-in-out infinite',
      },
      keyframes: {
        'mascote-float': {
          '0%, 100%': { transform: 'translateY(0)' },
          '50%': { transform: 'translateY(-4px)' },
        },
        'guia-pulse': {
          '0%, 100%': { transform: 'scale(1)', opacity: '0.5' },
          '50%': { transform: 'scale(1.08)', opacity: '0.25' },
        },
      },
    },
  },
  plugins: [],
}
