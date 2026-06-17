// 도메인 타입 — src/app/store/base.py·audit_store.py·telemetry_store.py 계약의 TS 미러.
// 키 구성/전이 규칙의 단일 진실원은 Python store. 여기서는 형태만 따른다.

export type JobStatus =
  | "pending"
  | "awaiting_approval"
  | "approved"
  | "running"
  | "done"
  | "failed"
  | "rejected";

export type JobSource = "slack" | "web" | "agent";

export interface Job {
  id: string;
  command: string;
  args: string;
  source: JobSource;
  status: JobStatus;
  requested_by: string;
  created_at: string;
  updated_at: string;
  channel?: string;
  diff?: string;
  result?: string;
  cost_usd?: number;
  tokens?: number;
  error?: string;
  approved_by?: string;
  approved_at?: string;
  trace_id?: string;
  rationale?: string;
}

export interface AuditEvent {
  job_id: string;
  ts: string;
  seq: number;
  action: string;
  actor: string;
  detail: string;
}

export interface Metric {
  job_id: string;
  ts: string;
  command?: string;
  duration_ms?: number;
  tokens?: number;
  cost_usd?: number;
  tool_calls?: number;
  success: boolean;
  error?: string;
}

// 종료 상태(더 이상 전이 없음) — store/base.py TERMINAL_STATUSES 미러.
export const TERMINAL_STATUSES: ReadonlySet<JobStatus> = new Set([
  "done",
  "failed",
  "rejected",
]);

export function isAwaitingApproval(job: Job): boolean {
  return job.status === "awaiting_approval";
}
