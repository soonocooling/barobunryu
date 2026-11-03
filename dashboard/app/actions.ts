"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import {
  deleteRule,
  deleteSplit,
  getTxn,
  pickableCategories,
  setTxnCategory,
  settledAmount,
  updateSetting,
  upsertSplit,
  type SplitDetail,
  type TxnDetail,
} from "@/lib/db";
import { planSplit } from "@/lib/split";

// 설정 키별 허용 범위 (밖이면 저장하지 않는다)
const SETTING_RULES: Record<string, { min: number; max: number; integer: boolean }> = {
  threshold: { min: 0, max: 1, integer: false },
  daily_ask_cap: { min: 0, max: 50, integer: true },
  digest_hour: { min: 0, max: 23, integer: true },
  split_suspect_min: { min: 0, max: 10_000_000, integer: true },
};

function parseNumber(raw: FormDataEntryValue | null, rule: (typeof SETTING_RULES)[string]) {
  if (typeof raw !== "string" || raw.trim() === "") return null;
  const n = Number(raw);
  if (!Number.isFinite(n) || n < rule.min || n > rule.max) return null;
  if (rule.integer && !Number.isInteger(n)) return null;
  return n;
}

export async function saveSettings(formData: FormData) {
  const updates: [string, string][] = [];
  for (const [key, rule] of Object.entries(SETTING_RULES)) {
    const n = parseNumber(formData.get(key), rule);
    if (n === null) redirect("/?msg=range");
    updates.push([key, String(n)]);
  }
  try {
    for (const [key, value] of updates) await updateSetting(key, value);
  } catch {
    redirect("/?msg=fail");
  }
  revalidatePath("/");
  redirect("/?msg=saved");
}

const splitOf = (t: TxnDetail): SplitDetail | null =>
  (Array.isArray(t.splits) ? t.splits[0] : t.splits) ?? null;

function optionalInt(raw: FormDataEntryValue | null): number | null {
  if (typeof raw !== "string" || raw.trim() === "") return null;
  return Number(raw);
}

function done(id: number, msg: string): never {
  revalidatePath("/");
  revalidatePath(`/txn/${id}`);
  redirect(`/txn/${id}?msg=${msg}`);
}

/** 거래 카테고리를 바꾸고 규칙을 학습한다. 정산으로 연결된 입금은 잔액과 어긋나므로 막는다. */
export async function changeCategory(formData: FormData) {
  const id = Number(formData.get("id"));
  const category = String(formData.get("category") ?? "");
  let result = "category";
  try {
    const txn = await getTxn(id);
    if (!txn) redirect("/");
    const allowed = pickableCategories(txn.direction).some((c) => c.code === category);
    if (txn.category === "settlement" || !allowed) result = "locked";
    else await setTxnCategory(txn, category);
  } catch (e) {
    if (isRedirect(e)) throw e;
    result = "fail";
  }
  done(id, result);
}

/** 더치페이를 만들거나 인원·내 몫을 고친다. 이미 받은 돈은 잔액에서 유지한다. */
export async function saveDutch(formData: FormData) {
  const id = Number(formData.get("id"));
  const n = optionalInt(formData.get("n"));
  const my = optionalInt(formData.get("my_share"));
  let result = "dutch";
  try {
    const txn = await getTxn(id);
    if (!txn) redirect("/");
    const split = splitOf(txn);
    const settled = split ? await settledAmount(split.id) : 0;
    const plan = txn.direction === "out" ? planSplit(txn.amount, n, my, settled) : "invalid";
    if (typeof plan === "string") result = plan === "settled" ? "settled" : "invalid";
    else await upsertSplit(txn, plan);
  } catch (e) {
    if (isRedirect(e)) throw e;
    result = "fail";
  }
  done(id, result);
}

/** 더치페이를 해제한다. 받은 돈 기록이 있으면 지우지 않는다. */
export async function removeDutch(formData: FormData) {
  const id = Number(formData.get("id"));
  let result = "undutch";
  try {
    const txn = await getTxn(id);
    if (!txn) redirect("/");
    const split = splitOf(txn);
    if (split && (await settledAmount(split.id)) > 0) result = "settled";
    else if (split) await deleteSplit(split.id);
  } catch (e) {
    if (isRedirect(e)) throw e;
    result = "fail";
  }
  done(id, result);
}

function isRedirect(e: unknown): boolean {
  return typeof (e as { digest?: unknown })?.digest === "string"
    && String((e as { digest: string }).digest).startsWith("NEXT_REDIRECT");
}

export async function removeRule(formData: FormData) {
  const id = Number(formData.get("id"));
  try {
    await deleteRule(id);
  } catch {
    redirect("/?msg=fail");
  }
  revalidatePath("/");
  redirect("/?msg=deleted");
}
