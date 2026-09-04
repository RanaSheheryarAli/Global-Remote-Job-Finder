import type { Metadata } from "next";
import "./globals.css";
import Navigation from "./navigation";

export const metadata: Metadata = {
  title: "Global Remote Job Tool",
  description: "Evidence-first remote job discovery",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <Navigation />
        {children}
      </body>
    </html>
  );
}
