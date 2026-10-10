/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./*/forms.py", "./static/js/*.js"],
  theme: {
    extend: {
      colors: {
        saffron: { DEFAULT: "#E8751A", light: "#F6C79C", dark: "#C75F0E" },
        maroon: { DEFAULT: "#7A1F2B", dark: "#5C1620" },
        gold: "#C9A227",
        cream: { DEFAULT: "#FFF8EE", dark: "#F3E6D0" },
        ink: "#2B2118",
      },
      fontFamily: {
        sans: ['"Noto Sans"', '"Noto Sans Devanagari"', "system-ui", "sans-serif"],
        serif: ['"Noto Serif"', '"Noto Serif Devanagari"', "Georgia", "serif"],
      },
    },
  },
  plugins: [],
};
