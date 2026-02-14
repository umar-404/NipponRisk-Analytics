/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#7b1fa2",
          50: "#f3e5f5",
          100: "#e1bee7",
          500: "#9c27b0",
          700: "#7b1fa2",
        },
      },
    },
  },
  plugins: [],
};