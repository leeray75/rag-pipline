import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { StoreProvider } from "@/store/provider";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "RAG Pipeline Dashboard",
  description: "AI Knowledge Base RAG Ingestion Pipeline",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <nav className="border-b">
          <div className="container mx-auto flex items-center gap-6 p-4">
            <a href="/" className="font-bold text-lg">RAG Pipeline</a>
            <a href="/ingestion" className="text-sm hover:underline">Ingestion</a>
            <a href="/staging" className="text-sm hover:underline">Staging</a>
            <a href="/review" className="text-sm hover:underline">Review</a>
            <a href="/audit" className="text-sm hover:underline">Audit</a>
            <a href="/loop" className="text-sm hover:underline">Loop Monitor</a>
          </div>
        </nav>
        <StoreProvider>{children}</StoreProvider>
      </body>
    </html>
  );
}
