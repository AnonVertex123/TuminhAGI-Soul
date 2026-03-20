/** @type {import('tailwindcss').Config} */
const config = {
  darkMode: "class",
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      boxShadow: {
        soft: "0 4px 6px -1px rgb(0 0 0 / 0.1)"
      },
      borderRadius: {
        xl2: "12px"
      }
    }
  },
  plugins: []
};

module.exports = config;

