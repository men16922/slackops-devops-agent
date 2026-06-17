import Link from "next/link";
import { listRecentJobs } from "../lib/ddb";
import { fmtCost, fmtTime } from "../lib/format";
import { NewCommand } from "./NewCommand";

// 요청 시점에 DynamoDB 조회 — 정적 캐시 금지.
export const dynamic = "force-dynamic";

export default async function JobsPage() {
  const jobs = await listRecentJobs(50);

  return (
    <>
      <h1>Job Queue</h1>
      <p className="page-sub">
        Slack/Web 두 producer 가 넣은 작업의 최신 피드 (GSI2 <span className="mono">FEED</span>).
      </p>

      <NewCommand />

      <div className="panel">
        {jobs.length === 0 ? (
          <div className="notice">
            작업이 없습니다. 시드가 실행됐는지(seed 컨테이너) 또는 DynamoDB 연결을 확인하세요.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Status</th>
                <th>Command</th>
                <th>Args</th>
                <th>Source</th>
                <th>Requested by</th>
                <th>Created</th>
                <th>Cost</th>
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
                  <td className="mono muted">{j.args || "—"}</td>
                  <td>
                    {j.source === "agent" ? (
                      <span className="src-agent">🤖 agent</span>
                    ) : (
                      j.source
                    )}
                  </td>
                  <td className="mono">{j.requested_by || "—"}</td>
                  <td className="muted">{fmtTime(j.created_at)}</td>
                  <td>{fmtCost(j.cost_usd)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
