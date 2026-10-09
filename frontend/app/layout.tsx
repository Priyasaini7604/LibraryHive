import "./globals.css";

import type { Metadata, Viewport } from "next";
import { Inter } from "next/font/google";
import { connection } from "next/server";

import { Providers } from "./providers";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });

export const metadata: Metadata = {
  title: { default: "LibraryHive", template: "%s · LibraryHive" },
  description: "Find a study library near you, see live seat availability and book your seat.",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#2563eb",
};

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  // Render per request so Next.js can apply the CSP nonce from proxy.ts (SECURITY.md section 8).
  await connection();
  return (
    <html lang="en" className={inter.variable}>
      <body className="min-h-dvh antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
