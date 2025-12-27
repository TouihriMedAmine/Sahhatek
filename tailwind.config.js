/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './static/js/**/*.js',
  ],
  darkMode: 'class', // enable class-based dark mode
  theme: {
    extend: {
      colors: {
        primary: '#2563eb', // blue accent for user messages / buttons
      },
      maxWidth: {
        'chat': '920px', // main chat content max width
      },
      spacing: {
        'sidebar': '18rem', // 72 * 4px = 288px, approximate width of sidebar
      },
      borderRadius: {
        'xl': '14px', // bubble rounding
      },
      boxShadow: {
        'chat': '0 6px 12px rgba(16,24,40,0.04)',
      },
    },
  },
  plugins: [],
};
