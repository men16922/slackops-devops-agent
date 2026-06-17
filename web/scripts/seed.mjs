// DynamoDB Local 시드 — 테이블 생성(deploy/dynamodb/create-table.sh 스키마 미러) + mock 데이터.
// 오프라인 로컬 개발/데모 전용. 실 DynamoDB 에는 실행하지 말 것(DDB_ENDPOINT 필수 가드).

import {
  CreateTableCommand,
  DescribeTableCommand,
  DynamoDBClient,
  ResourceInUseException,
} from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, PutCommand } from "@aws-sdk/lib-dynamodb";

const ENDPOINT = process.env.DDB_ENDPOINT;
const TABLE = process.env.DDB_TABLE ?? "slackops-agent";

if (!ENDPOINT) {
  console.error(
    "[seed] DDB_ENDPOINT 미설정 — 시드는 DynamoDB Local 전용입니다. 실 DynamoDB 보호를 위해 중단.",
  );
  process.exit(1);
}

const client = new DynamoDBClient({
  region: process.env.AWS_REGION ?? "us-east-1",
  endpoint: ENDPOINT,
  credentials: {
    accessKeyId: process.env.AWS_ACCESS_KEY_ID ?? "local",
    secretAccessKey: process.env.AWS_SECRET_ACCESS_KEY ?? "local",
  },
});
const doc = DynamoDBDocumentClient.from(client, {
  marshallOptions: { removeUndefinedValues: true },
});

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ── 시간 헬퍼(_util.py utcnow_iso/day_of 동형) ──
function isoAt(offsetSec = 0) {
  return new Date(Date.now() + offsetSec * 1000)
    .toISOString()
    .replace("Z", "000Z");
}
function dayOf(ts) {
  return ts.slice(0, 10).replace(/-/g, "");
}

async function waitReady() {
  for (let i = 0; i < 30; i++) {
    try {
      await client.send(new DescribeTableCommand({ TableName: "__probe__" }));
      return;
    } catch (e) {
      // ResourceNotFound = 서비스는 살아있음(준비 완료).
      if (e.name === "ResourceNotFoundException") return;
      await sleep(1000);
    }
  }
  throw new Error("[seed] DynamoDB Local 연결 시간 초과");
}

async function ensureTable() {
  try {
    await client.send(
      new CreateTableCommand({
        TableName: TABLE,
        BillingMode: "PAY_PER_REQUEST",
        AttributeDefinitions: [
          { AttributeName: "PK", AttributeType: "S" },
          { AttributeName: "SK", AttributeType: "S" },
          { AttributeName: "GSI1PK", AttributeType: "S" },
          { AttributeName: "GSI1SK", AttributeType: "S" },
          { AttributeName: "GSI2PK", AttributeType: "S" },
          { AttributeName: "GSI2SK", AttributeType: "S" },
        ],
        KeySchema: [
          { AttributeName: "PK", KeyType: "HASH" },
          { AttributeName: "SK", KeyType: "RANGE" },
        ],
        GlobalSecondaryIndexes: [
          {
            IndexName: "GSI1",
            KeySchema: [
              { AttributeName: "GSI1PK", KeyType: "HASH" },
              { AttributeName: "GSI1SK", KeyType: "RANGE" },
            ],
            Projection: { ProjectionType: "ALL" },
          },
          {
            IndexName: "GSI2",
            KeySchema: [
              { AttributeName: "GSI2PK", KeyType: "HASH" },
              { AttributeName: "GSI2SK", KeyType: "RANGE" },
            ],
            Projection: { ProjectionType: "ALL" },
          },
        ],
      }),
    );
    console.log(`[seed] table '${TABLE}' created`);
  } catch (e) {
    if (e instanceof ResourceInUseException) {
      console.log(`[seed] table '${TABLE}' already exists`);
    } else {
      throw e;
    }
  }
}

// ── mock 항목 빌더 ──
function jobItem(j) {
  return {
    PK: `JOB#${j.id}`,
    SK: "META",
    GSI1PK: `STATUS#${j.status}`,
    GSI1SK: j.created_at,
    GSI2PK: "FEED",
    GSI2SK: j.created_at,
    ...j,
  };
}
function auditItem(jobId, seq, ts, action, actor, detail = "") {
  return {
    PK: `JOB#${jobId}`,
    SK: `AUDIT#${ts}#${String(seq).padStart(6, "0")}`,
    GSI2PK: `AUDIT#${dayOf(ts)}`,
    GSI2SK: ts,
    job_id: jobId,
    ts,
    seq,
    action,
    actor,
    detail,
  };
}
function metricItem(jobId, ts, m) {
  return {
    PK: `JOB#${jobId}`,
    SK: `METRIC#${ts}`,
    GSI2PK: `METRIC#${dayOf(ts)}`,
    GSI2SK: ts,
    job_id: jobId,
    ts,
    ...m,
  };
}

async function put(item) {
  await doc.send(new PutCommand({ TableName: TABLE, Item: item }));
}

const DIFF_SAMPLE = `diff --git a/infra/main.tf b/infra/main.tf
index 8a1c0fe..b27d4aa 100644
--- a/infra/main.tf
+++ b/infra/main.tf
@@ -12,7 +12,7 @@ resource "aws_autoscaling_group" "api" {
-  min_size = 2
+  min_size = 3
   max_size = 10
   desired_capacity = 3
`;

const DIFF_AGENT_SAMPLE = `diff --git a/deploy/nginx/api.conf b/deploy/nginx/api.conf
index 3f2a1bc..9d4e5af 100644
--- a/deploy/nginx/api.conf
+++ b/deploy/nginx/api.conf
@@ -8,7 +8,7 @@ location /checkout {
   proxy_pass http://checkout_upstream;
-  proxy_read_timeout 30s;
+  proxy_read_timeout 60s;
   proxy_next_upstream error timeout;
`;

async function seedData() {
  const items = [];

  // 1) 승인 대기 PR 작업(데모 핵심) — diff 출력게이트.
  const pr = {
    id: "pr-1001",
    command: "pr",
    args: "scale api ASG min_size 2->3",
    source: "slack",
    status: "awaiting_approval",
    requested_by: "U_DEMO_LEE",
    channel: "C_DEVOPS",
    created_at: isoAt(-600),
    updated_at: isoAt(-540),
    diff: DIFF_SAMPLE,
  };
  items.push(jobItem(pr));
  items.push(auditItem(pr.id, 1, isoAt(-600), "enqueued", "U_DEMO_LEE"));
  items.push(auditItem(pr.id, 2, isoAt(-560), "claimed", "worker"));
  items.push(
    auditItem(pr.id, 3, isoAt(-540), "awaiting_approval", "worker", "diff posted"),
  );

  // 2) 완료된 diagnose.
  const diag = {
    id: "diag-1002",
    command: "diagnose",
    args: "payment-service",
    source: "slack",
    status: "done",
    requested_by: "U_DEMO_KIM",
    channel: "C_DEVOPS",
    created_at: isoAt(-1800),
    updated_at: isoAt(-1740),
    result: "CrashLoopBackOff: OOMKilled. memory limit 256Mi 권장 상향 → 512Mi.",
    cost_usd: 0.0231,
    tokens: 8420,
  };
  items.push(jobItem(diag));
  items.push(auditItem(diag.id, 1, isoAt(-1800), "enqueued", "U_DEMO_KIM"));
  items.push(auditItem(diag.id, 2, isoAt(-1790), "claimed", "worker"));
  items.push(auditItem(diag.id, 3, isoAt(-1740), "completed", "worker"));
  items.push(
    metricItem(diag.id, isoAt(-1740), {
      command: "diagnose",
      duration_ms: 18230,
      tokens: 8420,
      cost_usd: 0.0231,
      tool_calls: 6,
      success: true,
    }),
  );

  // 3) 진행 중 logs.
  const logs = {
    id: "logs-1003",
    command: "logs",
    args: "checkout-api",
    source: "web",
    status: "running",
    requested_by: "web-operator",
    created_at: isoAt(-120),
    updated_at: isoAt(-90),
  };
  items.push(jobItem(logs));
  items.push(auditItem(logs.id, 1, isoAt(-120), "enqueued", "web-operator"));
  items.push(auditItem(logs.id, 2, isoAt(-90), "claimed", "worker"));

  // 4) 완료된 tf-review.
  const tf = {
    id: "tf-1004",
    command: "tf-review",
    args: "",
    source: "slack",
    status: "done",
    requested_by: "U_DEMO_LEE",
    channel: "C_DEVOPS",
    created_at: isoAt(-3600),
    updated_at: isoAt(-3540),
    result: "위험 1건(보안그룹 0.0.0.0/0:22), 비용 +$48/mo, 승인 권장.",
    cost_usd: 0.0145,
    tokens: 5120,
  };
  items.push(jobItem(tf));
  items.push(auditItem(tf.id, 1, isoAt(-3600), "enqueued", "U_DEMO_LEE"));
  items.push(auditItem(tf.id, 2, isoAt(-3580), "claimed", "worker"));
  items.push(auditItem(tf.id, 3, isoAt(-3540), "completed", "worker"));
  items.push(
    metricItem(tf.id, isoAt(-3540), {
      command: "tf-review",
      duration_ms: 12110,
      tokens: 5120,
      cost_usd: 0.0145,
      tool_calls: 3,
      success: true,
    }),
  );

  // 5) 실패한 ping(드문 케이스).
  const ping = {
    id: "ping-1005",
    command: "ping",
    args: "",
    source: "slack",
    status: "failed",
    requested_by: "U_DEMO_KIM",
    channel: "C_DEVOPS",
    created_at: isoAt(-7200),
    updated_at: isoAt(-7180),
    error: "timeout: claude headless 무응답(300s)",
  };
  items.push(jobItem(ping));
  items.push(auditItem(ping.id, 1, isoAt(-7200), "enqueued", "U_DEMO_KIM"));
  items.push(auditItem(ping.id, 2, isoAt(-7195), "claimed", "worker"));
  items.push(auditItem(ping.id, 3, isoAt(-7180), "failed", "worker", "timeout"));
  items.push(
    metricItem(ping.id, isoAt(-7180), {
      command: "ping",
      duration_ms: 300000,
      tokens: 0,
      cost_usd: 0,
      tool_calls: 0,
      success: false,
      error: "timeout",
    }),
  );

  // 6) 에이전트 자율 제안 — 승인 대기 PR(diff + 근거). "감지→제안→사람 승인" 핵심 서사.
  const agentPr = {
    id: "agent-2001",
    command: "pr",
    args: "bump nginx proxy_read_timeout for /checkout 30s->60s",
    source: "agent",
    status: "awaiting_approval",
    requested_by: "agent",
    created_at: isoAt(-300),
    updated_at: isoAt(-280),
    diff: DIFF_AGENT_SAMPLE,
    rationale:
      "checkout-api 504 게이트웨이 타임아웃 급증(p99 8.1s) 감지 — proxy_read_timeout 상향 PR을 제안합니다. 승인 시에만 push/PR 생성(L1 출력 게이트).",
  };
  items.push(jobItem(agentPr));
  items.push(
    auditItem(agentPr.id, 1, isoAt(-300), "proposed", "agent", "504 spike detected"),
  );
  items.push(auditItem(agentPr.id, 2, isoAt(-290), "claimed", "worker"));
  items.push(
    auditItem(agentPr.id, 3, isoAt(-280), "awaiting_approval", "worker", "diff posted"),
  );

  // 7) 에이전트 제안 — 진단(PENDING, worker 픽업 전 = 막 올라온 제안).
  const agentDiag = {
    id: "agent-2002",
    command: "diagnose",
    args: "api",
    source: "agent",
    status: "pending",
    requested_by: "agent",
    created_at: isoAt(-60),
    updated_at: isoAt(-60),
    rationale: "api 5xx 오류율 12% 감지 — 다중 소스 종합 진단을 제안합니다.",
  };
  items.push(jobItem(agentDiag));
  items.push(
    auditItem(agentDiag.id, 1, isoAt(-60), "proposed", "agent", "error rate 12%"),
  );

  for (const item of items) await put(item);
  console.log(`[seed] inserted ${items.length} items`);
}

async function main() {
  console.log(`[seed] endpoint=${ENDPOINT} table=${TABLE}`);
  await waitReady();
  await ensureTable();
  // 테이블 ACTIVE 보장(로컬은 즉시지만 안전하게 짧게 대기).
  await sleep(500);
  await seedData();
  console.log("[seed] done");
}

main().catch((e) => {
  console.error("[seed] FAILED:", e);
  process.exit(1);
});
