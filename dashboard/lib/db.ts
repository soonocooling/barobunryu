import "server-only";

import keywords from "../../keywords.json";

// ---------------------------------------------------------------- 카테고리 (단일 출처: 루트 keywords.json)
type CategoryMap = Record<string, { label: string }>;
const CATEGORIES = (keywords as { categories: CategoryMap }).categories;

export function categoryLabel(code: string | null | undefined): string {
  if (!code || code === "unclassified") return "미분류";
  return CATEGORIES[code]?.label ?? code;
}

// ---------------------------------------------------------------- PostgREST
export type MonthlyRow = { month: string; category: string; spent: number; n: number };
export type SplitRow = {
  id: number;
  total: number;
  n: number;
  my_share: number;
  receivable: number;
  remaining: number;
  transactions: { cp_label: string | null; ts: string } | null;
};
export type PendingRow = {
  id: number;
  ts: string;
  amount: number;
  direction: "out" | "in";
  cp_label: string | null;
};
type TxnSplit = { n: number; total: number; my_share: number };
export type TxnRow = {
  id: number;
  ts: string;
  amount: number;
  direction: "out" | "in";
  category: string | null;
  cp_label: string | null;
  status: "auto" | "pending" | "confirmed";
  splits: TxnSplit | TxnSplit[] | null;
};
export type RuleRow = {
  id: number;
  cp_key: string;
  category: string;
  hits: number;
  counterparties: { alias: string | null } | null;
};

export class DbError extends Error {}

async function rest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const base = process.env.SUPABASE_URL?.replace(/\/$/, "");
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!base || !key) {
    throw new DbError("SUPABASE_URL / SUPABASE_SERVICE_KEY가 설정되지 않았어요.");
  }
  let res: Response;
  try {
    res = await fetch(`${base}/rest/v1/${path}`, {
      ...init,
      headers: {
        apikey: key,
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
        ...(init.headers ?? {}),
      },
      cache: "no-store",
    });
  } catch (e) {
    // 원문 예외에는 URL이 들어갈 수 있어 오류 코드만 꺼내 메시지를 새로 만든다.
    const code = (e as { cause?: { code?: string } }).cause?.code ?? (e as Error).name;
    throw new DbError(`데이터베이스에 연결하지 못했어요 (${code}).`);
  }
  if (!res.ok) {
    throw new DbError(
      `데이터베이스 요청이 실패했어요 (${res.status}, ${path.split("?")[0]}).`,
    );
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export function monthly(month: string) {
  return rest<MonthlyRow[]>(`monthly_summary?month=eq.${encodeURIComponent(month)}`);
}

export function monthTransactions(month: string) {
  const [y, m] = month.split("-").map(Number);
  const next = new Date(Date.UTC(y, m, 1));
  const end = `${next.getUTCFullYear()}-${String(next.getUTCMonth() + 1).padStart(2, "0")}`;
  const bound = (ym: string) => encodeURIComponent(`${ym}-01T00:00:00+09:00`);
  return rest<TxnRow[]>(
    `transactions?ts=gte.${bound(month)}&ts=lt.${bound(end)}` +
      "&select=id,ts,amount,direction,category,cp_label,status,splits(n,total,my_share)" +
      "&order=ts.desc&limit=100",
  );
}

export function openSplits() {
  return rest<SplitRow[]>(
    "splits?status=eq.open&select=*,transactions(cp_label,ts)&order=created_at.desc",
  );
}

export function pending() {
  return rest<PendingRow[]>("transactions?status=eq.pending&order=ts.desc&limit=20");
}

export function rules() {
  return rest<RuleRow[]>(
    "rules?active=eq.true&select=*,counterparties(alias)&order=hits.desc",
  );
}

export async function settings(): Promise<Record<string, string>> {
  const rows = await rest<{ key: string; value: string }[]>("settings?select=key,value");
  return Object.fromEntries(rows.map((r) => [r.key, r.value]));
}

export async function updateSetting(key: string, value: string): Promise<void> {
  await rest(`settings?key=eq.${encodeURIComponent(key)}`, {
    method: "PATCH",
    headers: { Prefer: "return=minimal" },
    body: JSON.stringify({ value }),
  });
}

export async function deleteRule(id: number): Promise<void> {
  if (!Number.isInteger(id) || id <= 0) throw new DbError("잘못된 규칙 번호예요.");
  await rest(`rules?id=eq.${id}`, { method: "DELETE", headers: { Prefer: "return=minimal" } });
}
