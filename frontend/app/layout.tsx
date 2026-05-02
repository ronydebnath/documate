import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "DocuMate — Fair Work assistant",
  description:
    "Plain-English answers about Australian workplace rules, with citations to Fair Work Ombudsman sources.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en-AU">
      <body className="font-sans text-zinc-900 antialiased">{children}</body>
    </html>
  );
}
