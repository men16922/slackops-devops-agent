import Link from "next/link";
import { notFound } from "next/navigation";
import { getJob, listAuditForJob } from "../../../lib/ddb";
import { fmtCost, fmtNum, fmtTime } from "../../../lib/format";
import { ApprovalButtons } from "./ApprovalButtons";

export const dynamic = "force-dynamic";

export default async function JobDetailPage({
  params,
}: {
  params: { id: string };
}) {
  const job = await getJob(params.id);
  if (!job) notFound();

  const audit = await listAuditForJob(params.id);

  return (
    <>
      <Link href="/" className="back">
        ← Jobs
      </Link>

      <h1>
        <span className="mono">{job.command}</span>{" "}
        <span className={`badge ${job.status}`}>{job.status}</span>
      </h1>
      <p className="page-sub mono">JOB#{job.id}</p>

      <div className="panel">
        <dl className="kv">
          <dt>Args</dt>
          <dd className="mono">{job.args || "—"}</dd>
          <dt>Source</dt>
          <dd>{job.source}</dd>
          <dt>Requested by</dt>
          <dd className="mono">{job.requested_by || "—"}</dd>
          <dt>Created</dt>
          <dd className="muted">{fmtTime(job.created_at)}</dd>
          <dt>Updated</dt>
          <dd className="muted">{fmtTime(job.updated_at)}</dd>
          <dt>Cost / Tokens</dt>
          <dd>
            {fmtCost(job.cost_usd)} · {fmtNum(job.tokens)} tok
          </dd>
          {job.approved_by && (
            <>
              <dt>Approved by</dt>
              <dd className="mono">
                {job.approved_by} @ {fmtTime(job.approved_at)}
              </dd>
            </>
          )}
          {job.result && (
            <>
              <dt>Result</dt>
              <dd>{job.result}</dd>
            </>
          )}
          {job.error && (
            <>
              <dt>Error</dt>
              <dd style={{ color: "var(--red)" }}>{job.error}</dd>
            </>
          )}
        </dl>
      </div>

      {job.status === "awaiting_approval" && (
        <>
          <h2>Output Gate — 승인 필요</h2>
          {job.diff && <pre className="diff">{job.diff}</pre>}
          <div style={{ marginTop: 14 }}>
            <ApprovalButtons id={job.id} />
          </div>
        </>
      )}

      <h2>Audit Timeline</h2>
      <div className="panel">
        {audit.length === 0 ? (
          <div className="notice">감사 이벤트 없음.</div>
        ) : (
          <ul className="timeline">
            {audit.map((e) => (
              <li key={`${e.ts}#${e.seq}`}>
                <span className="t-action">{e.action}</span>
                <span className="muted">{e.actor || "—"}</span>
                {e.detail && <span className="muted">· {e.detail}</span>}
                <span className="t-ts" style={{ marginLeft: "auto" }}>
                  {fmtTime(e.ts)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
