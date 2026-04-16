import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        mtg: {
          bg: "#0c0a14",
          surface: "#15121f",
          card: "#1a1625",
          border: "#2a2535",
          gold: "#c9a84c",
          "gold-light": "#e0c76a",
          "gold-dark": "#a08530",
          text: "#e8e6f0",
          subtle: "#7c7891",
          muted: "#4a4560",
          white: "#f9faf4",
          blue: "#0e68ab",
          black: "#150b00",
          red: "#d3202a",
          green: "#00733e",
        },
      },
      backgroundImage: {
        "gold-gradient":
          "linear-gradient(135deg, #c9a84c 0%, #e0c76a 50%, #c9a84c 100%)",
        "dark-gradient":
          "radial-gradient(ellipse at top, #1a1625 0%, #0c0a14 70%)",
      },
      boxShadow: {
        gold: "0 0 20px rgba(201, 168, 76, 0.15)",
        "gold-lg": "0 0 40px rgba(201, 168, 76, 0.2)",
        card: "0 4px 24px rgba(0, 0, 0, 0.4)",
      },
      animation: {
        "pulse-gold": "pulse-gold 2s ease-in-out infinite",
        "fade-in": "fade-in 0.3s ease-out",
        "slide-up": "slide-up 0.4s ease-out",
      },
      keyframes: {
        "pulse-gold": {
          "0%, 100%": { boxShadow: "0 0 20px rgba(201, 168, 76, 0.1)" },
          "50%": { boxShadow: "0 0 40px rgba(201, 168, 76, 0.3)" },
        },
        "fade-in": {
          from: { opacity: "0" },
          to: { opacity: "1" },
        },
        "slide-up": {
          from: { opacity: "0", transform: "translateY(12px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
export default config;
