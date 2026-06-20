"use client";

// 주기적 router.refresh() — force-dynamic 서버 컴포넌트(작업 피드/상세)를 재요청해
// 상태 전이(pending→running→done)를 새로고침 없이 반영한다(클라이언트 입력 상태는 보존).

import { useRouter } from "next/navigation";
import { useEffect } from "react";

export function AutoRefresh({ intervalMs = 4000 }: { intervalMs?: number }) {
  const router = useRouter();
  useEffect(() => {
    const h = setInterval(() => router.refresh(), intervalMs);
    return () => clearInterval(h);
  }, [router, intervalMs]);
  return null;
}
