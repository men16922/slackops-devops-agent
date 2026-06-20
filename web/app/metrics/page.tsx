import { listMetricsFeed } from "../../lib/ddb";
import { fmtCost, fmtNum, fmtTime } from "../../lib/format";
import type { Metric } from "../../lib/types";

export const dynamic = "force-dynamic";

interface CmdRollup {
  command: string;
  runs: number;
  cost: number;
  tokens: number;
  toolCalls: number;
  ok: number;
}

function rollupByCommand(metrics: Metric[]): CmdRollup[] {
  const map = new Map<string, CmdRollup>();
  for (const m of metrics) {
    const key = m.command ?? "(unknown)";
    const r =
      map.get(key) ??
      { command: key, runs: 0, cost: 0, tokens: 0, toolCalls: 0, ok: 0 };
    r.runs += 1;
    r.cost += m.cost_usd ?? 0;
    r.tokens += m.tokens ?? 0;
    r.toolCalls += m.tool_calls ?? 0;
    if (m.success) r.ok += 1;
    map.set(key, r);
  }
  return [...map.values()].sort((a, b) => b.runs - a.runs);
}

export default async function MetricsPage() {
  const metrics = await listMetricsFeed(2);

  const totalRuns = metrics.length;
  const totalCost = metrics.reduce((s, m) => s + (m.cost_usd ?? 0), 0);
  const totalTokens = metrics.reduce((s, m) => s + (m.tokens ?? 0), 0);
  const totalTools = metrics.reduce((s, m) => s + (m.tool_calls ?? 0), 0);
  const okRate =
    totalRuns === 0
      ? 0
      : Math.round((metrics.filter((m) => m.success).length / totalRuns) * 100);
  const rollup = rollupByCommand(metrics);

  return (
    <>
      <h1>Telemetry</h1>
      <p className="page-sub">
        OpenTelemetry metrics (last 2 days, GSI2 <span className="mono">METRIC#yyyymmdd</span>).
      </p>

      <div className="cards">
        <div className="card">
          <div className="label">Runs</div>
          <div className="value">{fmtNum(totalRuns)}</div>
        </div>
        <div className="card">
          <div className="label">Total cost</div>
          <div className="value">{fmtCost(totalCost)}</div>
        </div>
        <div className="card">
          <div className="label">Tokens</div>
          <div className="value">{fmtNum(totalTokens)}</div>
        </div>
        <div className="card">
          <div className="label">Tool calls</div>
          <div className="value">{fmtNum(totalTools)}</div>
        </div>
        <div className="card">
          <div className="label">Success rate</div>
          <div className="value">{okRate}%</div>
        </div>
      </div>

      <h2>By command</h2>
      <div className="panel">
        {rollup.length === 0 ? (
          <div className="notice">No metrics data.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Command</th>
                <th>Runs</th>
                <th>Success</th>
                <th>Cost</th>
                <th>Tokens</th>
                <th>Tool calls</th>
              </tr>
            </thead>
            <tbody>
              {rollup.map((r) => (
                <tr key={r.command}>
                  <td className="mono">{r.command}</td>
                  <td>{r.runs}</td>
                  <td>
                    {r.ok}/{r.runs}
                  </td>
                  <td>{fmtCost(r.cost)}</td>
                  <td>{fmtNum(r.tokens)}</td>
                  <td>{fmtNum(r.toolCalls)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <h2>Recent runs</h2>
      <div className="panel">
        {metrics.length === 0 ? (
          <div className="notice">No metrics data.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Command</th>
                <th>Duration</th>
                <th>Cost</th>
                <th>Tokens</th>
                <th>OK</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((m) => (
                <tr key={`${m.job_id}#${m.ts}`}>
                  <td className="muted">{fmtTime(m.ts)}</td>
                  <td className="mono">{m.command ?? "—"}</td>
                  <td>{m.duration_ms != null ? `${fmtNum(m.duration_ms)} ms` : "—"}</td>
                  <td>{fmtCost(m.cost_usd)}</td>
                  <td>{fmtNum(m.tokens)}</td>
                  <td>{m.success ? "✓" : "✗"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}
