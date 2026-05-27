import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#0b0d10",
        surface: "#13161b",
        "surface-2": "#1a1e25",
        border: "#262b33",
        muted: "#8a94a6",
        text: "#e6e9ef",
        accent: "#5b8def",
        "accent-hover": "#7aa1f2",
      },
      animation: {
        shimmer: "shimmer 1.6s linear infinite",
        spin: "spin 0.8s linear infinite",
      },
      keyframes: {
        shimmer: {
          "0%": { backgroundPosition: "-400px 0" },
          "100%": { backgroundPosition: "400px 0" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
