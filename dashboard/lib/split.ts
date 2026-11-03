// 더치페이 금액 계산. 봇(watch.py)의 apply_answer와 같은 규칙을 쓴다.
export type SplitPlan = {
  n: number;
  my_share: number;
  receivable: number;
  remaining: number;
  status: "open" | "done";
};
export type SplitError = "invalid" | "settled";

export function planSplit(
  amount: number,
  rawN: number | null,
  rawMy: number | null,
  settled: number,
): SplitPlan | SplitError {
  if (rawN === null && rawMy === null) return "invalid";
  if (rawN !== null && (!Number.isInteger(rawN) || rawN < 2 || rawN > 20)) return "invalid";
  if (rawMy !== null && (!Number.isInteger(rawMy) || rawMy <= 0 || rawMy >= amount)) return "invalid";
  const n = rawN ?? Math.max(2, Math.round(amount / (rawMy as number)));
  const my = rawMy ?? Math.ceil(amount / n);
  if (my >= amount) return "invalid";
  const receivable = amount - my;
  // 이미 받은 돈보다 받을 돈을 작게 만들면 정산 기록과 어긋난다.
  if (receivable < settled) return "settled";
  const remaining = receivable - settled;
  return { n, my_share: my, receivable, remaining, status: remaining === 0 ? "done" : "open" };
}
