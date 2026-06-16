// 표시용 포매터.

export function fmtTime(ts?: string): string {
  if (!ts) return "—";
  // "2026-06-16T12:34:56.789000Z" -> "06-16 12:34:56"
  return ts.slice(5, 19).replace("T", " ");
}

export function fmtCost(usd?: number): string {
  if (usd == null) return "—";
  return `$${usd.toFixed(4)}`;
}

export function fmtNum(n?: number): string {
  if (n == null) return "—";
  return n.toLocaleString("en-US");
}
