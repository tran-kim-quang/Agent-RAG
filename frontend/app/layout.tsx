import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agent-RAG Command Center",
  description: "Synthetic Intelligence Workspace for Agent-RAG operations.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
