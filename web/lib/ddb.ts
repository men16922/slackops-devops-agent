// DynamoDB 데이터 액세스 — 단일테이블 slackops-agent 읽기 + 승인 전이.
// 질의 패턴은 src/app/store/{dynamodb_store,audit_store,telemetry_store}.py 미러.
//
// 자격증명/엔드포인트:
//   - DDB_ENDPOINT 설정 시 → 로컬 DynamoDB Local (오프라인, 더미 키).
//   - 미설정 시 → 실 DynamoDB (Vercel/EC2). 자격증명은 AWS SDK 기본 체인
//     (env AWS_ACCESS_KEY_ID/SECRET 또는 IAM Role)에서 자동 해석.

import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import {
  DynamoDBDocumentClient,
  GetCommand,
  QueryCommand,
} from "@aws-sdk/lib-dynamodb";
import type {
  AuditEvent,
  ChatMessage,
  Conversation,
  Job,
  Metric,
} from "./types";
import { recentDays } from "./time";

export const TABLE = process.env.DDB_TABLE ?? "slackops-agent";

const raw = new DynamoDBClient({
  region: process.env.AWS_REGION ?? "ap-northeast-2",
  ...(process.env.DDB_ENDPOINT ? { endpoint: process.env.DDB_ENDPOINT } : {}),
});

export const doc = DynamoDBDocumentClient.from(raw, {
  marshallOptions: { removeUndefinedValues: true },
});

// ── readers ───────────────────────────────────────────────

export async function listRecentJobs(limit = 50): Promise<Job[]> {
  // GSI2 PK=FEED, 최신순 — dynamodb_store.py:list_recent 미러.
  const r = await doc.send(
    new QueryCommand({
      TableName: TABLE,
      IndexName: "GSI2",
      KeyConditionExpression: "GSI2PK = :pk",
      ExpressionAttributeValues: { ":pk": "FEED" },
      ScanIndexForward: false,
      Limit: limit,
    }),
  );
  return (r.Items ?? []).map((it) => it as Job);
}

export async function getJob(id: string): Promise<Job | null> {
  const r = await doc.send(
    new GetCommand({ TableName: TABLE, Key: { PK: `JOB#${id}`, SK: "META" } }),
  );
  return r.Item ? (r.Item as Job) : null;
}

export async function listAuditForJob(
  id: string,
  limit = 100,
): Promise<AuditEvent[]> {
  // PK=JOB#id & SK begins_with AUDIT# — audit_store.py:list_for_job 미러(시간순).
  const r = await doc.send(
    new QueryCommand({
      TableName: TABLE,
      KeyConditionExpression: "PK = :pk AND begins_with(SK, :sk)",
      ExpressionAttributeValues: { ":pk": `JOB#${id}`, ":sk": "AUDIT#" },
      ScanIndexForward: true,
      Limit: limit,
    }),
  );
  return (r.Items ?? []).map((it) => it as AuditEvent);
}

// ── 대화 버스(chat_store.py 미러) ──────────────────────────
export async function getConversation(
  convId: string,
): Promise<Conversation | null> {
  const r = await doc.send(
    new GetCommand({ TableName: TABLE, Key: { PK: `CHAT#${convId}`, SK: "META" } }),
  );
  return r.Item ? (r.Item as Conversation) : null;
}

export async function listChatMessages(convId: string): Promise<ChatMessage[]> {
  // PK=CHAT#conv & SK begins_with MSG# — 청크 리스트를 content 로 join(chat_store.py 미러).
  const r = await doc.send(
    new QueryCommand({
      TableName: TABLE,
      KeyConditionExpression: "PK = :pk AND begins_with(SK, :sk)",
      ExpressionAttributeValues: { ":pk": `CHAT#${convId}`, ":sk": "MSG#" },
      ScanIndexForward: true,
    }),
  );
  return (r.Items ?? []).map((it) => {
    const chunks = (it.chunks as string[] | undefined) ?? [];
    return {
      conv_id: it.conv_id,
      seq: it.seq,
      role: it.role,
      content: chunks.join(""),
      done: Boolean(it.done),
      created_at: it.created_at,
    } as ChatMessage;
  });
}

export async function listMetricsFeed(
  days = 2,
  limit = 200,
): Promise<Metric[]> {
  // GSI2 PK=METRIC#yyyymmdd — telemetry_store.py:list_feed 미러. 자정 경계 위해 최근 days 일 병합.
  const out: Metric[] = [];
  for (const day of recentDays(days)) {
    const r = await doc.send(
      new QueryCommand({
        TableName: TABLE,
        IndexName: "GSI2",
        KeyConditionExpression: "GSI2PK = :pk",
        ExpressionAttributeValues: { ":pk": `METRIC#${day}` },
        ScanIndexForward: false,
        Limit: limit,
      }),
    );
    for (const it of r.Items ?? []) out.push(it as Metric);
  }
  return out;
}
