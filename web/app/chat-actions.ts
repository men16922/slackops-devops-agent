"use server";

// 대화 producer(web) server action — store/chat_store.py:DynamoDbChatStore 의
// create_conversation / append_user_message 미러. 사용자 입력은 Claude 에 직접 전달되지
// 않고 DynamoDB 대화 버스에 적재된다 — 에이전트(chat_agent)가 폴링해 sanitizer 격리 후 처리.

import { randomUUID } from "node:crypto";
import { PutCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";
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
}

export async function sendUserMessage(
  convId: string,
  rawContent: string,
): Promise<SendResult> {
  const content = rawContent.trim();
  if (content.length === 0) return { ok: false, message: "메시지가 비어 있습니다." };
  if (content.length > CONTENT_MAX) {
    return { ok: false, message: `메시지가 너무 깁니다(최대 ${CONTENT_MAX}자).` };
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
      return { ok: false, message: "지금은 에이전트가 응답 중입니다. 잠시 후 다시." };
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
