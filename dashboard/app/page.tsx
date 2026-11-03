import {
  categoryLabel,
  monthly,
  openSplits,
  pending,
  rules,
  settings,
  type MonthlyRow,
  type PendingRow,
  type RuleRow,
  type SplitRow,
} from "@/lib/db";
import { removeRule, saveSettings } from "./actions";

export const dynamic = "force-dynamic";

const won = (n: number) => `${n.toLocaleString("ko-KR")}원`;

function kstMonth(date = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
  }).formatToParts(date);
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${get("year")}-${get("month")}`;
}

function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1 + delta, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

function shortDate(iso: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

async function safe<T>(job: Promise<T>): Promise<{ data: T | null; failed: boolean }> {
  try {
    return { data: await job, failed: false };
  } catch {
    return { data: null, failed: true };
  }
}

const MESSAGES: Record<string, { text: string; err?: boolean }> = {
  saved: { text: "설정을 저장했어요." },
  deleted: { text: "규칙을 삭제했어요." },
  range: { text: "설정 값 범위를 확인해 주세요.", err: true },
  fail: { text: "저장하지 못했어요. 잠시 뒤 다시 시도해 주세요.", err: true },
};

export default async function Home(props: PageProps<"/">) {
  const params = await props.searchParams;
  const rawMonth = typeof params.month === "string" ? params.month : "";
  const thisMonth = kstMonth();
  const month = /^\d{4}-(0[1-9]|1[0-2])$/.test(rawMonth) ? rawMonth : thisMonth;
  const msgKey = typeof params.msg === "string" ? params.msg : "";
  const msg = MESSAGES[msgKey];

  const [mon, splits, pend, ruleList, setting] = await Promise.all([
    safe(monthly(month)),
    safe(openSplits()),
    safe(pending()),
    safe(rules()),
    safe(settings()),
  ]);

  const anyFailed = [mon, splits, pend, ruleList, setting].some((r) => r.failed);

  const rows: MonthlyRow[] = [...(mon.data ?? [])].sort((a, b) => b.spent - a.spent);
  const totalSpent = rows.reduce((s, r) => s + r.spent, 0);
  const maxSpent = rows[0]?.spent ?? 0;

  const splitRows: SplitRow[] = splits.data ?? [];
  const receivable = splitRows.reduce((s, r) => s + r.remaining, 0);

  const pendRows: PendingRow[] = pend.data ?? [];
  const ruleRows: RuleRow[] = ruleList.data ?? [];
  const cfg = setting.data ?? {};

  return (
    <main>
      <header className="top">
        <h1>바로분류</h1>
        <nav className="month" aria-label="월 이동">
          <a href={`/?month=${shiftMonth(month, -1)}`}>◀</a>
          <span>{month}</span>
          <a href={`/?month=${shiftMonth(month, 1)}`} aria-disabled={month >= thisMonth}>
            ▶
          </a>
        </nav>
      </header>

      {msg && <div className={`notice ${msg.err ? "err" : "ok"}`}>{msg.text}</div>}
      {anyFailed && (
        <div className="notice err">
          일부 데이터를 불러오지 못했어요. 환경변수와 데이터베이스 연결을 확인해 주세요.
        </div>
      )}

      <section>
        <h2>{month} 순지출</h2>
        <p className="big">{won(totalSpent)}</p>
        {rows.length === 0 ? (
          <p className="empty">이 달에는 아직 기록된 지출이 없어요.</p>
        ) : (
          <ul className="bars">
            {rows.map((r) => (
              <li key={r.category}>
                <div className="row">
                  <span>
                    {categoryLabel(r.category)} <span className="muted">{r.n}건</span>
                  </span>
                  <span>{won(r.spent)}</span>
                </div>
                <div className="track">
                  <div
                    className="fill"
                    style={{ width: `${maxSpent ? Math.max(2, (r.spent / maxSpent) * 100) : 0}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
        <p className="muted" style={{ marginTop: 12 }}>
          엔빵은 내 몫만 포함하고, 계좌 이동과 입금은 뺀 금액이에요.
        </p>
      </section>

      <section>
        <h2>받을 돈</h2>
        {splitRows.length === 0 ? (
          <p className="empty">받을 돈이 없어요.</p>
        ) : (
          <>
            <ul className="list">
              {splitRows.map((s) => (
                <li key={s.id}>
                  <span className="name">
                    {s.transactions?.cp_label ?? "이름 없음"}{" "}
                    <span className="muted">
                      총 {won(s.total)} · {s.n}명
                    </span>
                  </span>
                  <span className="amount">{won(s.remaining)}</span>
                </li>
              ))}
            </ul>
            <div className="sum">
              <span>합계</span>
              <span>{won(receivable)}</span>
            </div>
          </>
        )}
      </section>

      <section>
        <h2>미분류 (최근 20건)</h2>
        {pendRows.length === 0 ? (
          <p className="empty">분류를 기다리는 거래가 없어요.</p>
        ) : (
          <ul className="list">
            {pendRows.map((t) => (
              <li key={t.id}>
                <span className="name">
                  {t.cp_label ?? "이름 없음"} <span className="muted">{shortDate(t.ts)}</span>
                </span>
                <span className="amount">
                  {t.direction === "in" ? "+" : ""}
                  {won(t.amount)}
                </span>
              </li>
            ))}
          </ul>
        )}
        <p className="muted" style={{ marginTop: 12 }}>
          텔레그램에서 답장하면 분류돼요.
        </p>
      </section>

      <section>
        <h2>학습된 규칙</h2>
        {ruleRows.length === 0 ? (
          <p className="empty">아직 학습된 규칙이 없어요.</p>
        ) : (
          <ul className="list">
            {ruleRows.map((r) => (
              <li key={r.id}>
                <span className="name">
                  {r.counterparties?.alias ?? r.cp_key.replace(/^m:/, "")} →{" "}
                  {categoryLabel(r.category)} <span className="muted">{r.hits}회</span>
                </span>
                <form action={removeRule}>
                  <input type="hidden" name="id" value={r.id} />
                  <button type="submit" className="ghost">
                    삭제
                  </button>
                </form>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2>설정</h2>
        <form action={saveSettings} className="settings">
          <label>
            확신 기준 (0~1)
            <input
              type="number"
              name="threshold"
              step="0.05"
              min="0"
              max="1"
              defaultValue={cfg.threshold ?? ""}
              required
            />
            <span className="hint">이 값보다 확신이 낮은 거래만 물어봐요.</span>
          </label>
          <label>
            하루 질문 상한 (건)
            <input
              type="number"
              name="daily_ask_cap"
              step="1"
              min="0"
              max="50"
              defaultValue={cfg.daily_ask_cap ?? ""}
              required
            />
          </label>
          <label>
            묶음 알림 시각 (0~23시)
            <input
              type="number"
              name="digest_hour"
              step="1"
              min="0"
              max="23"
              defaultValue={cfg.digest_hour ?? ""}
              required
            />
          </label>
          <label>
            엔빵 의심 최소 금액 (원)
            <input
              type="number"
              name="split_suspect_min"
              step="1000"
              min="0"
              defaultValue={cfg.split_suspect_min ?? ""}
              required
            />
          </label>
          <button type="submit">저장</button>
        </form>
      </section>

      <footer>장소 분류 데이터: Kakao Local API</footer>
    </main>
  );
}
