import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Football Analytics",
  description:
    "Analyse de matchs de football à partir de vidéos, assistée par IA.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="fr" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
