import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Signalight - 주식 시그널 대시보드",
  description: "한국 주식 매매 시그널 분석 대시보드",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko" className="dark">
      <body className="antialiased relative">
        {/* Ambient floating orbs */}
        <div className="orb orb-1" aria-hidden="true" />
        <div className="orb orb-2" aria-hidden="true" />
        <div className="orb orb-3" aria-hidden="true" />

        <div className="relative z-10">{children}</div>
      </body>
    </html>
  );
}
