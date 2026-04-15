import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Screen2Deck",
    template: "%s · Screen2Deck",
  },
  description:
    "Upload a Magic: The Gathering deck screenshot and get a validated, exportable deck list in seconds.",
  openGraph: {
    title: "Screen2Deck",
    description:
      "OCR and Scryfall-validated MTG deck extraction for MTGA, Moxfield, Archidekt and more.",
    type: "website",
  },
};

export const viewport: Viewport = {
  themeColor: "#0a0a0a",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
