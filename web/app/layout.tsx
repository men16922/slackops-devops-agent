import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { NotificationBell } from "./NotificationBell";

export const metadata: Metadata = {
  title: "SlackOps DevOps Agent — Dashboard",
  description: "Slack-controlled DevOps agent — job queue, audit & telemetry over DynamoDB",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ko">
      <body>
        <header className="topbar">
          <div className="brand">
            <span className="dot" />
            SlackOps <span className="muted">DevOps Agent</span>
          </div>
          <nav>
            <Link href="/">Jobs</Link>
            <Link href="/detections">Detections</Link>
            <Link href="/metrics">Metrics</Link>
          </nav>
          <div className="topbar-right">
            <NotificationBell />
            <div className="src muted">store: DynamoDB single-table</div>
          </div>
        </header>
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
