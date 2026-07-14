import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { NotificationBell } from "./NotificationBell";
import { AuthControls } from "./AuthControls";
import { getDashboardUser } from "../lib/auth";

export const metadata: Metadata = {
  title: "SlackOps DevOps Agent — Dashboard",
  description: "Slack-controlled DevOps agent — job queue, audit & telemetry over DynamoDB",
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getDashboardUser();
  return (
    <html lang="ko">
      <body>
        <header className="topbar">
          <div className="topbar-inner">
            <div className="brand">
              <span className="dot" />
              SlackOps <span className="muted">DevOps Agent</span>
            </div>
            {user && (
              <>
                <nav>
                  <Link href="/">Jobs</Link>
                  <Link href="/detections">Detections</Link>
                  <Link href="/metrics">Metrics</Link>
                </nav>
                <div className="topbar-right">
                  <NotificationBell />
                  <div className="conn" title="Connected to DynamoDB (single-table)">
                    <span className="conn-dot" />
                    DynamoDB
                    <span className="conn-sub">single-table</span>
                  </div>
                  <AuthControls login={user.login} />
                </div>
              </>
            )}
          </div>
        </header>
        <main className="container">{children}</main>
      </body>
    </html>
  );
}
