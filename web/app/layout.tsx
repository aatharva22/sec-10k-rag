import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "SEC 10-K Chat",
  description:
    "Ask grounded questions about Apple, Microsoft, Amazon, Tesla, and NVIDIA 10-K filings (FY2022–2024).",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-bg text-text">{children}</body>
    </html>
  );
}
