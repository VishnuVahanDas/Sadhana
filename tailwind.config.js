/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./*/forms.py", "./static/js/*.js"],
  theme: {
    extend: {
      // Colours come from CSS variables (static/src/input.css) so a theme can swap them.
      colors: {
        saffron: {
          DEFAULT: "rgb(var(--c-saffron) / <alpha-value>)",
          light: "rgb(var(--c-saffron-light) / <alpha-value>)",
          dark: "rgb(var(--c-saffron-dark) / <alpha-value>)",
          ink: "rgb(var(--c-saffron-ink) / <alpha-value>)",
        },
        maroon: {
          DEFAULT: "rgb(var(--c-maroon) / <alpha-value>)",
          dark: "rgb(var(--c-maroon-dark) / <alpha-value>)",
        },
        gold: "rgb(var(--c-gold) / <alpha-value>)",
        cream: {
          DEFAULT: "rgb(var(--c-cream) / <alpha-value>)",
          dark: "rgb(var(--c-cream-dark) / <alpha-value>)",
        },
        ink: "rgb(var(--c-ink) / <alpha-value>)",
        surface: "rgb(var(--c-surface) / <alpha-value>)",
        bar: {
          DEFAULT: "rgb(var(--c-bar) / <alpha-value>)",
          dark: "rgb(var(--c-bar-dark) / <alpha-value>)",
          ink: "rgb(var(--c-bar-ink) / <alpha-value>)",
        },
      },
      fontFamily: {
        sans: ['"Noto Sans"', '"Noto Sans Devanagari"', "system-ui", "sans-serif"],
        serif: ['"Noto Serif"', '"Noto Serif Devanagari"', "Georgia", "serif"],
      },
    },
  },
  plugins: [],
};
