import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MeowTOrrent — Your download space",
  description: "A focused torrent workspace. Manage downloads with your own companion engine.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">{children}</body>
    </html>
  );
}
