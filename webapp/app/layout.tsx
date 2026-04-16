import type { Metadata, Viewport } from "next";
import Link from "next/link";
import { Roboto, Cinzel, JetBrains_Mono } from "next/font/google";
import "./globals.css";

/* ManaTuner-style fonts. Roboto body (as served by manatuner.app),
 * Cinzel serif heading (the "ManaTuner" h1 signature), JetBrains Mono
 * for small technical badges. */
const roboto = Roboto({
  subsets: ["latin"],
  weight: ["300", "400", "500", "700"],
  variable: "--font-roboto",
  display: "swap",
});

const cinzel = Cinzel({
  subsets: ["latin"],
  weight: ["400", "600", "700"],
  variable: "--font-cinzel",
  display: "swap",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-jetbrains",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Screen2Deck — MTG Deck Scanner",
    template: "%s · Screen2Deck",
  },
  description:
    "Upload a Magic: The Gathering deck screenshot and get a Scryfall-validated, exportable deck list in seconds. Vision AI + Scryfall.",
  openGraph: {
    title: "Screen2Deck — MTG Deck Scanner",
    description:
      "OCR and Scryfall-validated MTG deck extraction for MTGA, Moxfield, Archidekt and TappedOut.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#F5F3EE" },
    { media: "(prefers-color-scheme: dark)", color: "#0D0D0F" },
  ],
  width: "device-width",
  initialScale: 1,
};

/* S2D logo mark — a stylized mana pentagon with a scan line */
function LogoMark({ className }: { className?: string }) {
  return (
    <span
      className={`relative inline-flex items-center justify-center rounded-full ${className ?? ""}`}
      aria-hidden="true"
    >
      <svg viewBox="0 0 40 40" className="w-full h-full">
        <defs>
          <linearGradient id="logoGradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#E0B23A" />
            <stop offset="25%" stopColor="#2F5BA8" />
            <stop offset="50%" stopColor="#4A2160" />
            <stop offset="75%" stopColor="#C62828" />
            <stop offset="100%" stopColor="#2E7D32" />
          </linearGradient>
        </defs>
        <circle
          cx="20"
          cy="20"
          r="18"
          fill="#ffffff"
          stroke="url(#logoGradient)"
          strokeWidth="2.5"
        />
        <path
          d="M20 9L22.472 15.528L29 16.472L24 21.472L25.18 28L20 24.528L14.82 28L16 21.472L11 16.472L17.528 15.528L20 9Z"
          fill="url(#logoGradient)"
        />
      </svg>
    </span>
  );
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`${roboto.variable} ${cinzel.variable} ${jetbrains.variable}`}
    >
      <body className="min-h-screen flex flex-col">
        <header className="sticky top-0 z-50 backdrop-blur-sm bg-mtg-bg/75 border-b border-mtg-border">
          <nav className="max-w-6xl mx-auto px-4 sm:px-6 h-16 flex items-center justify-between">
            <Link
              href="/"
              className="group flex items-center gap-3 transition-transform duration-300 ease-signature hover:-translate-y-0.5"
              aria-label="Screen2Deck — home"
            >
              <LogoMark className="w-9 h-9" />
              <span className="font-heading font-bold text-xl tracking-heading text-mtg-text">
                Screen2Deck
              </span>
            </Link>
            <div className="flex items-center gap-5 text-sm">
              <span className="hidden sm:inline font-mono text-xs text-mtg-muted">
                v2.4.0
              </span>
              <a
                href="https://github.com/gbordes77/Screen2Deck"
                target="_blank"
                rel="noopener noreferrer"
                className="text-mtg-subtle hover:text-mtg-text transition-colors"
              >
                GitHub
              </a>
            </div>
          </nav>
        </header>

        <main className="flex-1 relative">{children}</main>

        <footer className="border-t border-mtg-border py-8 mt-auto">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-mtg-muted">
            <p className="flex items-center gap-2">
              <span className="font-heading font-semibold text-mtg-subtle tracking-heading">
                Screen2Deck
              </span>
              <span aria-hidden="true">·</span>
              <span>Vision AI + Scryfall deck extraction</span>
            </p>
            <p className="text-center sm:text-right">
              Magic: The Gathering is a trademark of Wizards of the Coast.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
