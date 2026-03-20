import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Tự Minh",
  description: "Medical Diagnostic Dashboard"
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi">
      <body>{children}</body>
    </html>
  );
}
