import type { Metadata } from "next";
import {
  IBM_Plex_Mono,
  IBM_Plex_Sans,
  IBM_Plex_Sans_Devanagari,
  Source_Serif_4,
} from "next/font/google";

import { Providers } from "./providers";

import "./globals.css";

const sourceSerif = Source_Serif_4({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-source-serif",
});

const plexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--font-plex-sans",
});

const plexDevanagari = IBM_Plex_Sans_Devanagari({
  subsets: ["latin", "devanagari"],
  weight: ["400", "500", "600"],
  display: "swap",
  variable: "--font-plex-devanagari",
});

const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "600", "700"],
  display: "swap",
  variable: "--font-plex-mono",
});

export const metadata: Metadata = {
  title: "Samanvay",
  description:
    "Harmonization workbench for multi-source urban land records. Prototype for Smart India Hackathon 2026, problem statement 26013.",
  icons: {
    icon: [
      { url: "/favicon-32.png", sizes: "32x32", type: "image/png" },
      { url: "/favicon-16.png", sizes: "16x16", type: "image/png" },
    ],
    apple: "/icon-512.png",
  },
};

const fontVariables = [
  sourceSerif.variable,
  plexSans.variable,
  plexDevanagari.variable,
  plexMono.variable,
].join(" ");

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={fontVariables}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
