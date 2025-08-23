import "./globals.css";
export const metadata = { title: "Screen2Deck" };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (<html lang="fr"><body>{children}</body></html>);
}