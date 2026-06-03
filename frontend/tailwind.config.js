/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: "#070b14",
          panel: "#101827",
          border: "#23354f",
          text: "#e0ecff",
          positive: "#21c17a",
          negative: "#f74c62",
          warning: "#f2be42",
          accent: "#40b5ff"
        }
      }
    }
  },
  plugins: []
};
