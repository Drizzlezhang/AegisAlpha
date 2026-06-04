import type { Metadata } from "next";
import "./globals.css";
import TopBar from "@/components/layout/top-bar";
import LeftPanel from "@/components/layout/left-panel";
import RightPanel from "@/components/layout/right-panel";
import StatusBar from "@/components/layout/status-bar";
import ErrorBoundary from "@/components/layout/error-boundary";
import RealTimeProvider from "@/components/layout/real-time-provider";

export const metadata: Metadata = {
  title: "Aegis 2.0",
  description: "Personal US Stock/Options Trading Decision Assistant",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" data-theme="dark" className="h-full antialiased">
      <body className="h-full flex flex-col overflow-hidden">
        <ErrorBoundary>
          <RealTimeProvider>
            <TopBar />
            <div className="flex flex-1 overflow-hidden">
              <LeftPanel />
              <main className="flex-1 overflow-y-auto">{children}</main>
              <RightPanel />
            </div>
            <StatusBar />
          </RealTimeProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}
