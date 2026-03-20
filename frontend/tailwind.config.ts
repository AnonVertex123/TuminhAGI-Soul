import type { Config } from "tailwindcss";

const config: Config = {
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

export default config;

