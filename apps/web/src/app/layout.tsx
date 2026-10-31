import type { Metadata } from "next";
import { Alfa_Slab_One, DM_Sans, Source_Serif_4 } from "next/font/google";
import "./globals.css";

const fontDisplay = Alfa_Slab_One({
  weight: "400",
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

const fontSerif = Source_Serif_4({
  weight: ["400", "600", "700"],
  style: ["normal", "italic"],
  subsets: ["latin"],
  variable: "--font-serif",
  display: "swap",
});

const fontSans = DM_Sans({
  weight: ["400", "500", "700"],
  subsets: ["latin"],
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
      <body className="min-h-full flex flex-col bg-paper text-ink">{children}</body>
    </html>
  );
}
