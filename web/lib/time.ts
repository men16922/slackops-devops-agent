// 시간/파티션 헬퍼 — src/app/store/_util.py 의 utcnow_iso/day_of 와 동형.
// Python: "%Y-%m-%dT%H:%M:%S.%fZ" (마이크로초 6자리). JS toISOString 은 ms(3자리)라 000 패딩.

export function utcnowIso(): string {
  // 2026-06-16T12:34:56.789Z -> 2026-06-16T12:34:56.789000Z
  return new Date().toISOString().replace("Z", "000Z");
}

export function dayOf(ts: string): string {
  // ISO ts -> yyyymmdd
  return ts.slice(0, 10).replace(/-/g, "");
}

// 최근 n일의 yyyymmdd 파티션 키 목록(오늘부터 과거로). metric feed 가 일자 파티션이라 자정 경계 보정용.
export function recentDays(n: number): string[] {
  const out: string[] = [];
  const base = Date.now();
  for (let i = 0; i < n; i++) {
    const d = new Date(base - i * 86_400_000);
    out.push(d.toISOString().slice(0, 10).replace(/-/g, ""));
  }
  return out;
}
