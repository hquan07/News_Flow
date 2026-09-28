import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NewsPulse Intelligence",
  description: "Real-time news and social media intelligence dashboard.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
