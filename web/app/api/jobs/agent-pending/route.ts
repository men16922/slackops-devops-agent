// 에이전트 제안 알림 폴링 엔드포인트 — NotificationBell 이 주기적으로 호출(읽기 전용).
// 인바운드 없음(클라이언트가 폴링) → Socket Mode/인바운드 0 불변 유지, Vercel 에서도 동작.

import { NextResponse } from "next/server";
import { listPendingAgentJobs } from "../../../../lib/ddb";

export const dynamic = "force-dynamic";

export async function GET() {
  const jobs = await listPendingAgentJobs();
  return NextResponse.json({ jobs });
}
