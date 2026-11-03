"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { deleteRule, updateSetting } from "@/lib/db";

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
