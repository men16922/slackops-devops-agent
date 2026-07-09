import Link from "next/link";
import { listRecentJobs } from "../lib/ddb";
import { fmtCost, fmtTime } from "../lib/format";
import { AutoRefresh } from "./AutoRefresh";
import { Chat } from "./Chat";

// 요청 시점에 DynamoDB 조회 — 정적 캐시 금지.
export const dynamic = "force-dynamic";

export default async function JobsPage() {
  const jobs = await listRecentJobs(50);

  const count = (s: string) => jobs.filter((j) => j.status === s).length;
  const kpis = [
    { label: "Total jobs", value: String(jobs.length), tone: "" },
    { label: "Awaiting approval", value: String(count("awaiting_approval")), tone: "warn" },
    { label: "Running", value: String(count("running")), tone: "info" },
    { label: "Done", value: String(count("done")), tone: "ok" },
    {
      label: "Spend",
      value: fmtCost(jobs.reduce((s, j) => s + (j.cost_usd ?? 0), 0)),
      tone: "",
    },
  ];

  return (
    <>
      <AutoRefresh />
      <div className="page-head">
        <div>
          <h1>Job Queue</h1>
          <p className="page-sub">
            Chat with the agent to get job proposals (below); approve them to run on the shared Slack/Web queue (GSI2{" "}
            <span className="mono">FEED</span>).
          </p>
        </div>
        <span className="live" title="Auto-refreshing every 4s">
          <span className="live-dot" />
          Live
        </span>
      </div>

      <div className="cards kpis">
        {kpis.map((k) => (
          <div key={k.label} className={`card kpi ${k.tone}`}>
            <div className="label">{k.label}</div>
            <div className="value">{k.value}</div>
          </div>
        ))}
      </div>

      <Chat />

      <div className="panel">
        {jobs.length === 0 ? (
          <div className="notice">
            No jobs. Check that the seed ran (seed container) or the DynamoDB connection.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Status</th>
                <th>Command</th>
                <th>Proposal</th>
                <th>Source</th>
                <th>Requested by</th>
                <th>Created</th>
                <th className="num">Cost</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j) => (
                <tr key={j.id}>
                  <td>
                    <span className={`badge ${j.status}`}>{j.status}</span>
                  </td>
                  <td>
                    <Link href={`/jobs/${j.id}`} className="mono">
                      {j.command}
                    </Link>
                  </td>
                  {(() => {
                    // Proposal = pr 이면 변경 내용(args), 그 외엔 에이전트 제안 근거(rationale).
                    // 단순 read 명령(diagnose/logs)의 args(타깃)는 제안이 아니므로 표기하지 않음.
                    const proposal = (j.command === "pr" ? j.args : j.rationale)?.trim();
                    return (
                      <td className="proposal" title={proposal || undefined}>
                        {proposal || <span className="muted">—</span>}
                      </td>
                    );
                  })()}
                  <td>
                    <span className={`tag src-${j.source}`}>{j.source}</span>
                  </td>
                  <td className="mono">{j.requested_by || "—"}</td>
                  <td className="muted">{fmtTime(j.created_at)}</td>
                  <td className="num mono">{fmtCost(j.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
