"use server";

// 승인/거부 server action — dynamodb_store.py:_conditional_set + audit_store.py:append 미러.
// ConditionExpression(status=awaiting_approval) 으로 낙관적 락 → 중복/경합 전이 차단.
// 인증은 MVP 범위 밖: approver 는 고정값(USER_GUIDE.md 명시).

import { randomUUID } from "node:crypto";
import { PutCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import { revalidatePath } from "next/cache";
import { TABLE, doc } from "../lib/ddb";
import { dayOf, utcnowIso } from "../lib/time";

const APPROVER = process.env.DASHBOARD_APPROVER ?? "web-operator";
const REQUESTER = process.env.DASHBOARD_APPROVER ?? "web-operator";

export interface ActionResult {
  ok: boolean;
  message?: string;
}

// 웹 producer 가 큐에 넣을 수 있는 명령 — allowlist.py:_COMMAND_TOOLS 와 동일 집합(+ping).
// default deny: 이 집합 밖 명령은 거부(주입 방어 — Slack/web 입력 직접 전달 금지).
const ALLOWED_COMMANDS = ["ping", "logs", "diagnose", "tf-review", "pr"] as const;
type AllowedCommand = (typeof ALLOWED_COMMANDS)[number];

// 인자가 필수인 명령(빈 인자 거부). tf-review/ping 은 인자 불필요.
const ARGS_REQUIRED: ReadonlySet<string> = new Set(["logs", "diagnose", "pr"]);

const ARGS_MAX = 280;

async function transition(
  id: string,
  newStatus: "approved" | "rejected",
): Promise<ActionResult> {
  const now = utcnowIso();
  try {
    await doc.send(
      new UpdateCommand({
        TableName: TABLE,
        Key: { PK: `JOB#${id}`, SK: "META" },
        UpdateExpression:
          "SET #s = :new, GSI1PK = :gpk, updated_at = :now, approved_by = :by, approved_at = :now",
        ConditionExpression: "#s = :expected",
        ExpressionAttributeNames: { "#s": "status" },
        ExpressionAttributeValues: {
          ":new": newStatus,
          ":gpk": `STATUS#${newStatus}`,
          ":now": now,
          ":by": APPROVER,
          ":expected": "awaiting_approval",
        },
      }),
    );
  } catch (e: unknown) {
    if (e instanceof Error && e.name === "ConditionalCheckFailedException") {
      return { ok: false, message: "이미 처리된 작업입니다(승인 대기 상태가 아님)." };
    }
    throw e;
  }

  // audit append (append-only) — SK=AUDIT#{ts}#{seq:06d}, GSI2=AUDIT#{yyyymmdd}/{ts}.
  const ts = utcnowIso();
  const seq = 1;
  await doc.send(
    new PutCommand({
      TableName: TABLE,
      Item: {
        PK: `JOB#${id}`,
        SK: `AUDIT#${ts}#${String(seq).padStart(6, "0")}`,
        GSI2PK: `AUDIT#${dayOf(ts)}`,
        GSI2SK: ts,
        job_id: id,
        ts,
        seq,
        action: newStatus,
        actor: APPROVER,
        detail: "via web dashboard",
      },
    }),
  );

  revalidatePath(`/jobs/${id}`);
  revalidatePath("/");
  return { ok: true };
}

export async function approveJob(id: string): Promise<ActionResult> {
  return transition(id, "approved");
}

export async function rejectJob(id: string): Promise<ActionResult> {
  return transition(id, "rejected");
}

// 웹 producer — 명령을 큐(JOB#…/META, status=pending, source=web)에 넣는다.
// dynamodb_store.py:enqueue + _to_item 미러. 실행은 worker 담당(여기선 적재만).
export async function enqueueJob(
  rawCommand: string,
  rawArgs: string,
): Promise<ActionResult> {
  const command = rawCommand.trim();
  const args = rawArgs.trim();

  // default deny — 알려진 명령만 허용(주입 방어: 자유 텍스트를 Claude 에 직접 전달하지 않음).
  if (!ALLOWED_COMMANDS.includes(command as AllowedCommand)) {
    return { ok: false, message: `허용되지 않은 명령입니다: ${command || "(빈값)"}` };
  }
  if (ARGS_REQUIRED.has(command) && args.length === 0) {
    return { ok: false, message: `'${command}' 는 인자가 필요합니다 (예: 서비스명/설명).` };
  }
  if (args.length > ARGS_MAX) {
    return { ok: false, message: `인자가 너무 깁니다(최대 ${ARGS_MAX}자).` };
  }

  const id = randomUUID();
  const now = utcnowIso();
  await doc.send(
    new PutCommand({
      TableName: TABLE,
      Item: {
        PK: `JOB#${id}`,
        SK: "META",
        GSI1PK: "STATUS#pending",
        GSI1SK: now,
        GSI2PK: "FEED",
        GSI2SK: now,
        id,
        command,
        args,
        source: "web",
        status: "pending",
        requested_by: REQUESTER,
        created_at: now,
        updated_at: now,
      },
    }),
  );

  revalidatePath("/");
  return { ok: true, message: `큐에 추가됨: ${command}` };
}
