import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "El Orientador",
  description: "Orientação acadêmica: perguntas, lacunas e evidências verificadas.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="pt-BR" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
