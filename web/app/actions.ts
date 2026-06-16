"use server";

// 승인/거부 server action — dynamodb_store.py:_conditional_set + audit_store.py:append 미러.
// ConditionExpression(status=awaiting_approval) 으로 낙관적 락 → 중복/경합 전이 차단.
// 인증은 MVP 범위 밖: approver 는 고정값(USER_GUIDE.md 명시).

import { PutCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import { revalidatePath } from "next/cache";
import { TABLE, doc } from "../lib/ddb";
import { dayOf, utcnowIso } from "../lib/time";

const APPROVER = process.env.DASHBOARD_APPROVER ?? "web-operator";

export interface ActionResult {
  ok: boolean;
  message?: string;
}

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
