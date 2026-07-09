"use client";

// 에이전트 자율 제안 알림 벨 — /api/jobs/agent-pending 를 주기적으로 폴링해 열린 제안을
// 보여준다(Chat.tsx 폴링 패턴 미러). lastSeen 워터마크는 localStorage(ISO created_at —
// 사전식 비교 == 시간순). 읽기 전용 폴링이라 인바운드 0 유지(Vercel 배포본에서도 동작).

import Link from "next/link";
import { useEffect, useState } from "react";
import type { Job } from "../lib/types";

const POLL_MS = 4000;
const STORAGE_KEY = "slackops_notif_seen";

export function NotificationBell() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [open, setOpen] = useState(false);
  const [lastSeen, setLastSeen] = useState("");

  // 새로고침해도 "본 시점" 유지 — 워터마크를 localStorage 에서 복원.
  useEffect(() => {
    setLastSeen(window.localStorage.getItem(STORAGE_KEY) ?? "");
  }, []);

  useEffect(() => {
    let stop = false;
    async function tick() {
      try {
        const r = await fetch("/api/jobs/agent-pending", { cache: "no-store" });
        if (!r.ok || stop) return;
        const data = (await r.json()) as { jobs: Job[] };
        if (!stop) setJobs(data.jobs ?? []);
      } catch {
        /* 폴링 실패는 다음 tick 에서 복구 */
      }
    }
    void tick();
    const h = setInterval(tick, POLL_MS);
    return () => {
      stop = true;
      clearInterval(h);
    };
  }, []);

  const unread = jobs.filter((j) => j.created_at > lastSeen).length;

  function markAllSeen() {
    const newest = jobs.reduce(
      (m, j) => (j.created_at > m ? j.created_at : m),
      lastSeen,
    );
    setLastSeen(newest);
    window.localStorage.setItem(STORAGE_KEY, newest);
  }

  return (
    <div className="notif">
      <button
        className="notif-bell"
        onClick={() => setOpen((o) => !o)}
        aria-label="Agent proposals"
      >
        <svg
          width="19"
          height="19"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
        {unread > 0 && <span className="notif-badge">{unread}</span>}
      </button>
      {open && (
        <div className="notif-dropdown">
          <div className="notif-head">
            <span>Agent proposals</span>
            {jobs.length > 0 && (
              <button className="notif-seen" onClick={markAllSeen}>
                Mark all seen
              </button>
            )}
          </div>
          {jobs.length === 0 ? (
            <p className="notif-empty">No pending agent proposals</p>
          ) : (
            jobs.map((j) => (
              <Link
                key={j.id}
                href={`/jobs/${j.id}`}
                className={`notif-item${j.created_at > lastSeen ? " unread" : ""}`}
                onClick={() => setOpen(false)}
              >
                <span className="notif-cmd">
                  <span className="tag src-agent">agent</span>
                  <span className="mono">{j.command}</span>
                </span>
                {j.args ? <code>{j.args}</code> : null}
                {j.rationale ? (
                  <span className="notif-why">{j.rationale}</span>
                ) : null}
              </Link>
            ))
          )}
        </div>
      )}
    </div>
  );
}
