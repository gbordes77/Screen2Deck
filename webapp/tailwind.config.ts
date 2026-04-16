import type { Config } from "tailwindcss";

/**
 * Design tokens aligned with the live manatuner.app homepage (light mode).
 *
 * Visual reference: https://www.manatuner.app/og-image-v3.jpg
 * - Soft lavender / off-white parchment background.
 * - Cinzel serif h1 with a WUBRG (white→blue→black→red→green) gradient.
 * - Roboto body (as served by manatuner.app).
 * - Pastel feature chips + two big rounded-full CTAs (gold + navy).
 * - Five mana symbol circles in the header row.
 */
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        /* Canonical MTG mana palette (used for h1 gradient + circles) */
        mana: {
          white: "#E0B23A",   // warm gold (W plains tone, deeper than cream for legibility on light bg)
          blue: "#2F5BA8",    // Island deep blue
          black: "#4A2160",   // Swamp dark purple (so it reads on parchment, not pure #150B00)
          red: "#C62828",     // Mountain red
          green: "#2E7D32",   // Forest green
          "white-soft": "#F5E8B3",
          "blue-soft": "#E3EDF8",
          "black-soft": "#EBE0F2",
          "red-soft": "#FBE4E4",
          "green-soft": "#E4EFE4",
        },
        /* Surfaces — light parchment theme */
        mtg: {
          bg: "#F5F3EE",       // parchment
          "bg-soft": "#FAF8F3", // lighter parchment (cards over bg)
          surface: "#FFFFFF",
          card: "#FFFFFF",
          border: "rgba(60,50,40,0.10)",
          "border-hover": "rgba(60,50,40,0.22)",
          text: "#1A1A1A",      // near-black for WCAG AA on parchment
          subtle: "#555555",
          muted: "#7a6f5f",

          /* Accents */
          gold: "#DAA520",
          "gold-light": "#E9B54C",
          "gold-dark": "#A07D14",
          navy: "#2D3E8E",       // CTA secondary (Browse the Library style)
          "navy-light": "#3F52B0",
          "navy-dark": "#1E2A6B",
        },
      },
      backgroundImage: {
        /* Signature h1 gradient: WUBRG sweep */
        "brand-wubrg":
          "linear-gradient(90deg, #E0B23A 0%, #2F5BA8 25%, #4A2160 50%, #C62828 75%, #2E7D32 100%)",
        /* Gold CTA — warm and slightly 3D */
        "cta-gold":
          "linear-gradient(135deg, #F4C542 0%, #E9B54C 55%, #D79922 100%)",
        /* Navy CTA */
        "cta-navy":
          "linear-gradient(135deg, #3F52B0 0%, #2D3E8E 55%, #1E2A6B 100%)",
        /* Page background: soft parchment with subtle gradient shine */
        "page-parchment":
          "radial-gradient(ellipse 100% 70% at 50% 0%, rgba(230,220,255,0.45) 0%, transparent 60%), linear-gradient(180deg, #F8F6F2 0%, #F1EDE4 100%)",
        /* Soft info callout */
        "callout-lavender":
          "linear-gradient(135deg, rgba(200,200,240,0.30) 0%, rgba(220,210,240,0.18) 100%)",
      },
      boxShadow: {
        sm: "0 1px 2px rgba(60,50,40,0.06), 0 1px 3px rgba(60,50,40,0.04)",
        md: "0 2px 4px rgba(60,50,40,0.06), 0 4px 8px rgba(60,50,40,0.06)",
        lg: "0 4px 8px rgba(60,50,40,0.08), 0 12px 24px rgba(60,50,40,0.08)",
        xl: "0 8px 16px rgba(60,50,40,0.10), 0 24px 48px rgba(60,50,40,0.10)",
        hover: "0 10px 30px rgba(60,50,40,0.12)",
        "glow-gold": "0 0 0 4px rgba(233,181,76,0.15)",
        "glow-navy": "0 0 0 4px rgba(63,82,176,0.15)",
        "cta-gold":
          "0 10px 24px rgba(218,165,32,0.28), inset 0 1px 0 rgba(255,255,255,0.50)",
        "cta-navy":
          "0 10px 24px rgba(45,62,142,0.28), inset 0 1px 0 rgba(255,255,255,0.15)",
      },
      borderRadius: {
        sm: "4px",
        md: "8px",
        lg: "12px",
        xl: "16px",
        "2xl": "20px",
        full: "9999px",
      },
      fontFamily: {
        /* next/font sets --font-* CSS vars from layout.tsx */
        sans: ["var(--font-roboto)", "Roboto", "system-ui", "sans-serif"],
        heading: ["var(--font-cinzel)", "Cinzel", "Playfair Display", "serif"],
        mono: ["var(--font-jetbrains)", "JetBrains Mono", "Fira Code", "monospace"],
      },
      letterSpacing: {
        tightest: "-0.02em",
        heading: "0.02em",
        wide2: "0.06em",
      },
      transitionTimingFunction: {
        signature: "cubic-bezier(0.4, 0, 0.2, 1)",
      },
      animation: {
        "fade-in": "fadeIn 0.5s cubic-bezier(0.4, 0, 0.2, 1) both",
        "slide-up": "slideInUp 0.6s cubic-bezier(0.4, 0, 0.2, 1) both",
        "scale-in": "scaleIn 0.4s cubic-bezier(0.4, 0, 0.2, 1) both",
        "pulse-soft": "pulseSoft 2.4s ease-in-out infinite",
        float: "float 6s ease-in-out infinite",
      },
      keyframes: {
        fadeIn: {
          from: { opacity: "0", transform: "translateY(8px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        slideInUp: {
          from: { opacity: "0", transform: "translateY(24px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        scaleIn: {
          from: { opacity: "0", transform: "scale(0.94)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        pulseSoft: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.7" },
        },
        float: {
          "0%, 100%": { transform: "translateY(0)" },
          "50%": { transform: "translateY(-6px)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
