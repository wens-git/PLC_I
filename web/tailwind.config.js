export default {
  content: ['./index.html', './src/**/*.{vue,js}'],
  theme: {
    colors: {
      transparent: 'transparent', current: 'currentColor',
      root: '#F6F8FA', panel: '#FFFFFF', card: '#FFFFFF', hover: '#EAF0F6', border: '#D8DEE6',
      primary: '#1F2933', secondary: '#5F6B7A', disabled: '#A6B0BC', accent: '#0B6BCB',
      ok: '#188038', warn: '#9A6700', danger: '#D1242F',
    },
    fontFamily: { sans: ['Microsoft YaHei UI', 'Microsoft YaHei', 'sans-serif'], mono: ['Consolas', 'monospace'] },
    fontSize: { xs: '12px', sm: '13px', base: '14px', lg: '16px', xl: '20px', '2xl': '28px' },
    extend: {},
  },
  plugins: [],
}
