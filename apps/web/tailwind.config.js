/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          50: "#f7f8fa",
          100: "#eef1f5",
          200: "#dfe4ec",
          300: "#c6cdd9",
          400: "#8b95a8",
          500: "#5b667a",
          600: "#3f4a5e",
          700: "#2c3546",
          800: "#1d2534",
          900: "#131a26",
        },
        accent: {
          50: "#eef7ff",
          100: "#d9edff",
          500: "#1a6dd4",
          600: "#1558ab",
          700: "#124a91",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Noto Sans",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
