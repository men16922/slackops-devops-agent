"use server";

// 대화 producer(web) server action — store/chat_store.py:DynamoDbChatStore 의
// create_conversation / append_user_message 미러. 사용자 입력은 Claude 에 직접 전달되지
// 않고 DynamoDB 대화 버스에 적재된다 — 에이전트(chat_agent)가 폴링해 sanitizer 격리 후 처리.

import { randomUUID } from "node:crypto";
import { GetCommand, PutCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";
import { TABLE, doc } from "../lib/ddb";
import { utcnowIso } from "../lib/time";

const CONTENT_MAX = 2000;

function msgSk(seq: number): string {
  return `MSG#${String(seq).padStart(6, "0")}`;
}

export async function createConversation(): Promise<{ convId: string }> {
  const id = randomUUID();
  const now = utcnowIso();
  await doc.send(
    new PutCommand({
      TableName: TABLE,
      Item: {
        PK: `CHAT#${id}`,
        SK: "META",
        GSI1PK: "CHATSTATUS#open",
        GSI1SK: now,
        GSI2PK: "CHATFEED",
        GSI2SK: now,
        id,
        status: "open",
        created_at: now,
        updated_at: now,
        msg_count: 0,
      },
    }),
  );
  return { convId: id };
}

export interface SendResult {
  ok: boolean;
  message?: string;
  seq?: number;
  // "gone" = 대화가 더 이상 없음(예: in-memory DynamoDB 재시드로 소멸) → 클라이언트가 새 대화로 복구.
  code?: "gone" | "busy";
}

export async function sendUserMessage(
  convId: string,
  rawContent: string,
): Promise<SendResult> {
  const content = rawContent.trim();
  if (content.length === 0) return { ok: false, message: "Message is empty." };
  if (content.length > CONTENT_MAX) {
    return { ok: false, message: `Message too long (max ${CONTENT_MAX} chars).` };
  }

  const now = utcnowIso();
  // msg_count 원자 증가 + status=awaiting_agent (STREAMING 중에는 거부 — 가드).
  let seq: number;
  try {
    const r = await doc.send(
      new UpdateCommand({
        TableName: TABLE,
        Key: { PK: `CHAT#${convId}`, SK: "META" },
        UpdateExpression:
          "ADD msg_count :one SET #s = :await, GSI1PK = :gpk, updated_at = :now",
        ConditionExpression: "attribute_exists(PK) AND #s <> :streaming",
        ExpressionAttributeNames: { "#s": "status" },
        ExpressionAttributeValues: {
          ":one": 1,
          ":await": "awaiting_agent",
          ":gpk": "CHATSTATUS#awaiting_agent",
          ":now": now,
          ":streaming": "streaming",
        },
        ReturnValues: "UPDATED_NEW",
      }),
    );
    seq = Number(r.Attributes?.msg_count) - 1;
  } catch (e) {
    const err = e as { name?: string };
    if (err.name === "ConditionalCheckFailedException") {
      // 조건 실패는 두 경우 — (a) 대화 자체가 없음(소멸), (b) 스트리밍 중. 존재 여부로 구분한다.
      const got = await doc.send(
        new GetCommand({ TableName: TABLE, Key: { PK: `CHAT#${convId}`, SK: "META" } }),
      );
      if (!got.Item) {
        return { ok: false, code: "gone", message: "Conversation not found — starting a new one." };
      }
      return { ok: false, code: "busy", message: "The agent is responding right now. Try again shortly." };
    }
    throw e;
  }

  await doc.send(
    new PutCommand({
      TableName: TABLE,
      Item: {
        PK: `CHAT#${convId}`,
        SK: msgSk(seq),
        conv_id: convId,
        seq,
        role: "user",
        chunks: [content],
        done: true,
        created_at: now,
      },
    }),
  );
  return { ok: true, seq };
}
