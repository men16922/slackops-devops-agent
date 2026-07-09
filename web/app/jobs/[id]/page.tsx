import Link from "next/link";
import { notFound } from "next/navigation";
import { getJob, listAuditForJob } from "../../../lib/ddb";
import { fmtCost, fmtNum, fmtTime } from "../../../lib/format";
import { ApprovalButtons } from "./ApprovalButtons";
import { AutoRefresh } from "../../AutoRefresh";
import { Markdown } from "../../Markdown";

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
      <AutoRefresh />
      <Link href="/" className="back">
        ← Jobs
      </Link>

      <h1>
        <span className="mono">{job.command}</span>{" "}
        <span className={`badge ${job.status}`}>{job.status}</span>
      </h1>
      <p className="page-sub mono">JOB#{job.id}</p>

      {job.source === "agent" && (
        <div className="panel rationale">
          <div className="rationale-label">Autonomous agent proposal</div>
          <p>
            {job.rationale ??
              "The ops agent observed the system and proposed this job. It runs only after human approval."}
          </p>
        </div>
      )}

      <div className="panel">
        <dl className="kv">
          <dt>Args</dt>
          <dd className="mono">{job.args || "—"}</dd>
          <dt>Source</dt>
          <dd>
            <span className={`tag src-${job.source}`}>{job.source}</span>
          </dd>
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
          {job.error && (
            <>
              <dt>Error</dt>
              <dd style={{ color: "var(--red)" }}>{job.error}</dd>
            </>
          )}
        </dl>
      </div>

      {job.result && (
        <>
          <h2>Result</h2>
          <div className="panel">
            <Markdown text={job.result} />
          </div>
        </>
      )}

      {job.status === "awaiting_approval" && (
        <>
          <h2>Output Gate — approval required</h2>
          {job.diff && <pre className="diff">{job.diff}</pre>}
          <div style={{ marginTop: 14 }}>
            <ApprovalButtons id={job.id} />
          </div>
        </>
      )}

      <h2>Audit Timeline</h2>
      <div className="panel">
        {audit.length === 0 ? (
          <div className="notice">No audit events.</div>
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
