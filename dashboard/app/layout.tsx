import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "바로분류",
  description: "애매한 거래만 결제 직후 묻는 가계부 봇의 대시보드",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}
