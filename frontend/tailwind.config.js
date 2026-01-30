/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'bg-main': '#f8fafc',
        'bg-sidebar': '#f1f5f9',
        'bg-card': '#ffffff',
        'border-custom': '#e2e8f0',
        'accent': '#2563eb',
        'accent-light': '#dbeafe',
        'text-main': '#1e293b',
        'text-muted': '#64748b',
        'profit-up': '#059669',
        'profit-down': '#dc2626',
      },
    },
  },
  plugins: [],
}
