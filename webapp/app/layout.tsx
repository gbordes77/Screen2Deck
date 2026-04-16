import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Screen2Deck — MTG Deck Scanner",
    template: "%s · Screen2Deck",
  },
  description:
    "Upload a Magic: The Gathering deck screenshot and get a validated, exportable deck list in seconds. Powered by Vision AI and Scryfall.",
  openGraph: {
    title: "Screen2Deck — MTG Deck Scanner",
    description:
      "OCR and Scryfall-validated MTG deck extraction for MTGA, Moxfield, Archidekt and more.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#0c0a14",
  width: "device-width",
  initialScale: 1,
};

function ManaIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
    >
      <path d="M12 2L15.09 8.26L22 9.27L17 14.14L18.18 21.02L12 17.77L5.82 21.02L7 14.14L2 9.27L8.91 8.26L12 2Z" />
    </svg>
  );
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col">
        <header className="border-b border-mtg-border/50 bg-mtg-surface/80 backdrop-blur-sm sticky top-0 z-50">
          <nav className="max-w-6xl mx-auto px-4 sm:px-6 h-14 flex items-center justify-between">
            <Link
              href="/"
              className="flex items-center gap-2 text-mtg-gold hover:text-mtg-gold-light transition-colors"
            >
              <ManaIcon className="w-6 h-6" />
              <span className="font-bold text-lg tracking-tight">
                Screen2Deck
              </span>
            </Link>
            <div className="flex items-center gap-4 text-sm text-mtg-subtle">
              <span className="hidden sm:inline">v2.4.0</span>
              <a
                href="https://github.com/gbordes77/Screen2Deck"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-mtg-text transition-colors"
              >
                GitHub
              </a>
            </div>
          </nav>
        </header>

        <main className="flex-1">{children}</main>

        <footer className="border-t border-mtg-border/50 py-6 mt-auto">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-mtg-muted">
            <p>
              Screen2Deck &mdash; Vision AI + Scryfall deck extraction
            </p>
            <p>
              Magic: The Gathering is a trademark of Wizards of the Coast
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
