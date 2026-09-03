import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Global Remote Job Tool",
  description: "Evidence-first remote job discovery",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

