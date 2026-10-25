import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "ThinkBuddy – স্মার্ট শিখন ও অভিভাবক সঙ্গী (Smart Learning Companion)",
  description:
    "জাতীয় শিক্ষাক্রম অনুযায়ী শ্রেণি ৬ থেকে ১২শ শ্রেণির শিক্ষার্থীদের জন্য বুদ্ধিমান রুটিন, প্র্যাকটিস কুইজ ও এআই পাঠ্যবই সহায়ক।",
  applicationName: "ThinkBuddy",
  manifest: "/manifest.json",
  icons: {
    icon: "/favicon.ico",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
  themeColor: "#2563EB",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="bn" suppressHydrationWarning>
      <head>
        <link rel="manifest" href="/manifest.json" />
      </head>
      <body>{children}</body>
    </html>
  );
}
