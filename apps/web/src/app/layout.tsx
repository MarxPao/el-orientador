import type { Metadata } from "next";
import localFont from "next/font/local";
import "./globals.css";
import { RouteProgress } from "@/components/route-progress";

// Fontes empacotadas no projeto (sem Google Fonts): o build e o uso funcionam offline.
const fontDisplay = localFont({
  src: [{ path: "./fonts/AlfaSlabOne-400.woff2", weight: "400", style: "normal" }],
  variable: "--font-display",
  display: "swap",
});

const fontSerif = localFont({
  src: [
    { path: "./fonts/SourceSerif4-var.woff2", weight: "200 900", style: "normal" },
    { path: "./fonts/SourceSerif4-var-italic.woff2", weight: "200 900", style: "italic" },
  ],
  variable: "--font-serif",
  display: "swap",
});

const fontSans = localFont({
  src: [{ path: "./fonts/DMSans-var.woff2", weight: "100 1000", style: "normal" }],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "El Orientador",
  description: "Orientação acadêmica: perguntas, lacunas e evidências verificadas.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="pt-BR"
      className={`h-full antialiased ${fontDisplay.variable} ${fontSerif.variable} ${fontSans.variable}`}
    >
      <body className="min-h-full flex flex-col bg-paper text-ink">
        <RouteProgress />
        {children}
      </body>
    </html>
  );
}
