import Link from "next/link";
import { listRecentJobs } from "../lib/ddb";
import { fmtCost, fmtTime } from "../lib/format";
import { Chat } from "./Chat";

// 요청 시점에 DynamoDB 조회 — 정적 캐시 금지.
export const dynamic = "force-dynamic";

export default async function JobsPage() {
  const jobs = await listRecentJobs(50);

  return (
    <>
      <h1>Job Queue</h1>
      <p className="page-sub">
        Chat with the agent to get job proposals (below); approve them to run on the shared Slack/Web queue (GSI2{" "}
        <span className="mono">FEED</span>).
      </p>

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
