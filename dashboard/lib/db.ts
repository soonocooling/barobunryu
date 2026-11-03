import "server-only";

import keywords from "../../keywords.json";

// ---------------------------------------------------------------- 카테고리 (단일 출처: 루트 keywords.json)
type CategoryMap = Record<string, { label: string; ask?: boolean }>;
const CATEGORIES = (keywords as { categories: CategoryMap }).categories;

export function categoryLabel(code: string | null | undefined): string {
  if (!code || code === "unclassified") return "미분류";
  return CATEGORIES[code]?.label ?? code;
}

/** 사용자가 고를 수 있는 카테고리. 출금은 일반 항목과 계좌 이동, 입금은 수입·계좌 이동·기타다. */
export function pickableCategories(direction: "out" | "in"): { code: string; label: string }[] {
  const codes =
    direction === "in"
      ? ["income", "self", "etc"]
      : [...Object.keys(CATEGORIES).filter((c) => CATEGORIES[c].ask !== false), "self"];
  return codes.map((code) => ({ code, label: categoryLabel(code) }));
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
export type TxnDetail = Omit<TxnRow, "splits"> & {
  method: "card" | "transfer";
  cp_key: string;
  splits: SplitDetail | SplitDetail[] | null;
};
export type SplitDetail = TxnSplit & {
  id: number;
  receivable: number;
  remaining: number;
  status: "open" | "done";
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
      "&order=ts.desc&limit=1000",
  );
}

export async function getTxn(id: number): Promise<TxnDetail | null> {
  if (!Number.isInteger(id) || id <= 0) return null;
  const rows = await rest<TxnDetail[]>(
    `transactions?id=eq.${id}&select=id,ts,amount,direction,method,category,cp_key,cp_label,status,` +
      "splits(id,n,total,my_share,receivable,remaining,status)",
  );
  return rows[0] ?? null;
}

export async function settledAmount(splitId: number): Promise<number> {
  const rows = await rest<{ amount: number }[]>(`settlements?split_id=eq.${splitId}&select=amount`);
  return rows.reduce((s, r) => s + r.amount, 0);
}

function patchTxn(id: number, values: Record<string, unknown>) {
  return rest(`transactions?id=eq.${id}`, {
    method: "PATCH",
    headers: { Prefer: "return=minimal" },
    body: JSON.stringify(values),
  });
}

/** classify.learn과 같은 규칙. 같은 분류 2회부터 켜지고, 분류가 바뀌면 1회로 돌아간다. */
async function learn(cpKey: string, category: string): Promise<void> {
  if (["etc", "transfer", "income", "settlement"].includes(category)) return;
  const key = encodeURIComponent(cpKey);
  const rows = await rest<{ category: string; hits: number }[]>(
    `rules?cp_key=eq.${key}&select=category,hits`,
  );
  if (rows.length === 0) {
    await rest("rules", {
      method: "POST",
      headers: { Prefer: "return=minimal" },
      body: JSON.stringify({ cp_key: cpKey, category, hits: 1, active: false }),
    });
    return;
  }
  const hits = rows[0].category === category ? rows[0].hits + 1 : 1;
  await rest(`rules?cp_key=eq.${key}`, {
    method: "PATCH",
    headers: { Prefer: "return=minimal" },
    body: JSON.stringify({ category, hits, active: hits >= 2 }),
  });
}

export async function setTxnCategory(txn: TxnDetail, category: string): Promise<void> {
  // 이미 확정된 같은 분류를 다시 저장해도 학습 횟수를 올리지 않는다(봇과 같은 조건).
  if (txn.status === "confirmed" && txn.category === category) return;
  await patchTxn(txn.id, { category, status: "confirmed", confidence: 1 });
  await learn(txn.cp_key, category);
}

export async function upsertSplit(
  txn: TxnDetail,
  plan: { n: number; my_share: number; receivable: number; remaining: number; status: string },
): Promise<void> {
  await rest("splits?on_conflict=txn_id", {
    method: "POST",
    headers: { Prefer: "resolution=merge-duplicates,return=minimal" },
    body: JSON.stringify({ txn_id: txn.id, total: txn.amount, ...plan }),
  });
  // 봇과 같이 용도를 모르는 거래의 더치페이는 식비로 본다.
  const unknown = !txn.category || txn.category === "transfer" || txn.category === "etc";
  const category = unknown ? "food" : (txn.category as string);
  await setTxnCategory(txn, category);
}

export async function deleteSplit(splitId: number): Promise<void> {
  await rest(`splits?id=eq.${splitId}`, {
    method: "DELETE",
    headers: { Prefer: "return=minimal" },
  });
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
