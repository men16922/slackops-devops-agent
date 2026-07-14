// 대화 폴링 엔드포인트 — 클라이언트(Chat)가 ~800ms 간격으로 메시지/상태를 가져온다.
// 읽기 전용(DynamoDB). 에이전트는 인바운드로 web 을 호출하지 않는다(Socket Mode 불변).

import { NextResponse } from "next/server";
import { getConversation, listChatMessages } from "../../../../lib/ddb";
import { getDashboardUser } from "../../../../lib/auth";

export const dynamic = "force-dynamic";

export async function GET(
  _req: Request,
  { params }: { params: { conv: string } },
) {
  const user = await getDashboardUser();
  if (!user) return NextResponse.json({ error: "Authentication required." }, { status: 401 });
  const conversation = await getConversation(params.conv);
  if (!conversation || conversation.requested_by !== user.login) {
    return NextResponse.json({ conversation: null, messages: [] }, { status: 404 });
  }
  const [, messages] = await Promise.all([
    Promise.resolve(conversation),
    listChatMessages(params.conv),
  ]);
  return NextResponse.json({ conversation, messages });
}
