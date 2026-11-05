import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "NetAccess Systems Nigeria",
  description: "Reliable broadband plans from NetAccess Systems Nigeria.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link href="https://fonts.googleapis.com/css2?family=Barlow+Semi+Condensed:wght@500;600;700;800&family=DM+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
      </head>
      <body>{children}</body>
    </html>
  );
}
