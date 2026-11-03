import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "바로분류",
  description: "애매한 거래만 결제 직후 묻는 가계부 봇의 대시보드",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko">
      <head>
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/npm/pretendard@1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css"
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
