// 대화 폴링 엔드포인트 — 클라이언트(Chat)가 ~800ms 간격으로 메시지/상태를 가져온다.
// 읽기 전용(DynamoDB). 에이전트는 인바운드로 web 을 호출하지 않는다(Socket Mode 불변).

import { NextResponse } from "next/server";
import { getConversation, listChatMessages } from "../../../../lib/ddb";

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  { params }: { params: { conv: string } },
) {
  const [conversation, messages] = await Promise.all([
    getConversation(params.conv),
    listChatMessages(params.conv),
  ]);
  return NextResponse.json({ conversation, messages });
}
