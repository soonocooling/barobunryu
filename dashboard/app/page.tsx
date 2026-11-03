import Link from "next/link";

import {
  categoryLabel,
  monthly,
  monthTransactions,
  openSplits,
  pending,
  rules,
  settings,
  type MonthlyRow,
  type PendingRow,
  type RuleRow,
  type SplitRow,
  type TxnRow,
} from "@/lib/db";
import { removeRule, saveSettings } from "./actions";
import { CategoryIcon } from "./icons";

export const dynamic = "force-dynamic";

const TZ = "Asia/Seoul";
const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"];
const LEGEND_LIMIT = 3;

const won = (n: number) => `${n.toLocaleString("ko-KR")}원`;

function kstDate(date: Date | string = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date(date));
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1 + delta, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

function shortDate(iso: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: TZ,
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

function dayLabel(ymd: string): string {
  const [y, m, d] = ymd.split("-").map(Number);
  return `${d}일 ${WEEKDAYS[new Date(Date.UTC(y, m - 1, d)).getUTCDay()]}요일`;
}

async function safe<T>(job: Promise<T>): Promise<{ data: T | null; failed: boolean }> {
  try {
    return { data: await job, failed: false };
  } catch (e) {
    // 원인은 서버 로그에만 남긴다(상태 코드·테이블 이름뿐, 키는 포함되지 않는다).
    console.error("[dashboard]", e instanceof Error ? e.message : "알 수 없는 오류");
    return { data: null, failed: true };
  }
}

const MESSAGES: Record<string, { text: string; err?: boolean }> = {
  saved: { text: "설정을 저장했어요." },
  deleted: { text: "규칙을 삭제했어요." },
  range: { text: "설정 값 범위를 확인해 주세요.", err: true },
  fail: { text: "저장하지 못했어요. 잠시 뒤 다시 시도해 주세요.", err: true },
};

const splitOf = (t: TxnRow) => (Array.isArray(t.splits) ? t.splits[0] : t.splits) ?? null;

/** 내 지출로 잡히는 금액. 더치페이는 내 몫만, 입금과 계좌 이동은 0이다. */
function mySpend(t: TxnRow): number {
  if (t.direction !== "out" || t.category === "self") return 0;
  return splitOf(t)?.my_share ?? t.amount;
}

/** 달력 칸. 1일 앞의 빈칸은 null이다. */
function monthCells(month: string): (string | null)[] {
  const [y, m] = month.split("-").map(Number);
  const first = new Date(Date.UTC(y, m - 1, 1)).getUTCDay();
  const last = new Date(Date.UTC(y, m, 0)).getUTCDate();
  const days = Array.from({ length: last }, (_, i) => `${month}-${String(i + 1).padStart(2, "0")}`);
  return [...Array<null>(first).fill(null), ...days];
}

function TxnItem({ t }: { t: TxnRow }) {
  const split = splitOf(t);
  const incoming = t.direction === "in";
  const name = t.cp_label ?? "이름 없음";
  const detail = split
    ? `더치페이 ${split.n}명 · 총 ${won(split.total)}`
    : categoryLabel(t.category);
  return (
    <li>
      <Link href={`/txn/${t.id}`} className="txn">
        <CategoryIcon code={t.category} />
        <div className="txn-body">
          <p className={`txn-amount${incoming ? " in" : ""}`}>
            {incoming ? "+" : "-"}
            {won(split?.my_share ?? t.amount)}
          </p>
          <p className="txn-sub">
            {name} · {detail}
            {t.status === "pending" && <span className="chip">확인 필요</span>}
          </p>
        </div>
        <span className="chev" aria-hidden="true" />
      </Link>
    </li>
  );
}

export default async function Home(props: PageProps<"/">) {
  const params = await props.searchParams;
  const rawMonth = typeof params.month === "string" ? params.month : "";
  const today = kstDate();
  const thisMonth = today.slice(0, 7);
  const month = /^\d{4}-(0[1-9]|1[0-2])$/.test(rawMonth) ? rawMonth : thisMonth;
  const rawDay = typeof params.day === "string" ? params.day : "";
  const selectedDay = /^\d{4}-\d{2}-\d{2}$/.test(rawDay) && rawDay.startsWith(month) ? rawDay : "";
  const msgKey = typeof params.msg === "string" ? params.msg : "";
  const msg = MESSAGES[msgKey];

  const [mon, txnList, splits, pend, ruleList, setting] = await Promise.all([
    safe(monthly(month)),
    safe(monthTransactions(month)),
    safe(openSplits()),
    safe(pending()),
    safe(rules()),
    safe(settings()),
  ]);

  const anyFailed = [mon, txnList, splits, pend, ruleList, setting].some((r) => r.failed);

  const rows: MonthlyRow[] = [...(mon.data ?? [])].sort((a, b) => b.spent - a.spent);
  const totalSpent = rows.reduce((s, r) => s + r.spent, 0);
  const top = rows[0];

  // 막대와 범례는 같은 항목을 쓴다. 상위 3개 뒤는 "그 외"로 묶는다.
  const named = rows.length > LEGEND_LIMIT + 1 ? rows.slice(0, LEGEND_LIMIT) : rows;
  const others = rows.slice(named.length);
  const othersSpent = others.reduce((s, r) => s + r.spent, 0);

  const txns: TxnRow[] = txnList.data ?? [];
  const saved = txns.reduce((s, t) => {
    const split = splitOf(t);
    return s + (split ? split.total - split.my_share : 0);
  }, 0);

  const byDay = new Map<string, TxnRow[]>();
  const spentByDay = new Map<string, number>();
  for (const t of txns) {
    const day = kstDate(t.ts);
    byDay.set(day, [...(byDay.get(day) ?? []), t]);
    spentByDay.set(day, (spentByDay.get(day) ?? 0) + mySpend(t));
  }

  const splitRows: SplitRow[] = splits.data ?? [];
  const receivable = splitRows.reduce((s, r) => s + r.remaining, 0);

  const pendRows: PendingRow[] = pend.data ?? [];
  const ruleRows: RuleRow[] = ruleList.data ?? [];
  const cfg = setting.data ?? {};

  return (
    <main>
      <header className="top">
        <nav className="month" aria-label="월 이동">
          <a href={`/?month=${shiftMonth(month, -1)}`} aria-label="이전 달" className="tri prev" />
          <span>{Number(month.slice(5))}월</span>
          <a
            href={`/?month=${shiftMonth(month, 1)}`}
            aria-label="다음 달"
            aria-disabled={month >= thisMonth}
            className="tri next"
          />
        </nav>
      </header>

      {msg && <div className={`notice ${msg.err ? "err" : "ok"}`}>{msg.text}</div>}
      {anyFailed && (
        <div className="notice err">
          일부 데이터를 불러오지 못했어요. 환경변수와 데이터베이스 연결을 확인해 주세요.
        </div>
      )}

      <section className="summary">
        <div className="totals">
          <div>
            <p className="label">순지출</p>
            <p className="value">{totalSpent ? `-${won(totalSpent)}` : "0원"}</p>
          </div>
          <div>
            <p className="label">받을 돈</p>
            <p className="value">{won(receivable)}</p>
          </div>
        </div>
        {saved > 0 && (
          <p className="headline">
            더치페이로 <em>{won(saved)}</em> 덜 쓴 걸로 잡았어요
          </p>
        )}
      </section>

      <section className="plain">
        <p className="label">소비 분석</p>
        {!top ? (
          <p className="empty">이 달에는 아직 기록된 지출이 없어요.</p>
        ) : (
          <>
            <h2 className="title">
              <em>{categoryLabel(top.category)}</em>에 가장 많은 돈을 썼어요
            </h2>
            <div className="stack" role="img" aria-label="카테고리별 지출 비율. 금액은 아래 목록에 있어요.">
              {named.map((r) => (
                <span
                  key={r.category}
                  className={`seg cat-${r.category}`}
                  style={{ flexGrow: r.spent }}
                  title={`${categoryLabel(r.category)} ${won(r.spent)}`}
                />
              ))}
              {othersSpent > 0 && (
                <span
                  className="seg neutral"
                  style={{ flexGrow: othersSpent }}
                  title={`그 외 ${others.length}개 ${won(othersSpent)}`}
                />
              )}
            </div>
            <ul className="legend">
              {named.map((r) => (
                <li key={r.category}>
                  <span className="who">
                    <span className={`dot cat-${r.category}`} />
                    {categoryLabel(r.category)}
                  </span>
                  <span className="amt">{won(r.spent)}</span>
                </li>
              ))}
              {othersSpent > 0 && (
                <li>
                  <span className="who">
                    <span className="dot neutral" />그 외 {others.length}개
                  </span>
                  <span className="amt">{won(othersSpent)}</span>
                </li>
              )}
            </ul>
            <p className="note">더치페이는 내 몫만 넣고, 계좌 이동과 입금은 뺀 금액이에요.</p>
          </>
        )}
      </section>

      {pendRows.length > 0 && (
        <section className="plain">
          <p className="label">확인이 필요해요</p>
          <h2 className="title">
            <em>{pendRows.length}건</em>이 답을 기다려요
          </h2>
          <ul className="rows">
            {pendRows.map((t) => (
              <li key={t.id}>
                <span>
                  {t.cp_label ?? "이름 없음"}
                  <small>{shortDate(t.ts)}</small>
                </span>
                <span className="amt">
                  {t.direction === "in" ? "+" : "-"}
                  {won(t.amount)}
                </span>
              </li>
            ))}
          </ul>
          <p className="note">텔레그램에서 답장하면 분류돼요.</p>
        </section>
      )}

      <section className="plain">
        <p className="label">더치페이</p>
        {splitRows.length === 0 ? (
          <p className="empty">받을 돈이 없어요.</p>
        ) : (
          <>
            <h2 className="title">
              <em>{won(receivable)}</em>을 더 받아야 해요
            </h2>
            <ul className="rows">
              {splitRows.map((s) => (
                <li key={s.id}>
                  <span>
                    {s.transactions?.cp_label ?? "이름 없음"}
                    <small>
                      총 {won(s.total)} · {s.n}명
                    </small>
                  </span>
                  <span className="amt">{won(s.remaining)}</span>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

      <section className="plain history" id="history">
        <p className="label">소비 내역</p>
        <div className="calendar" aria-label="일별 순지출 달력">
          {WEEKDAYS.map((w) => (
            <span key={w} className="wd">
              {w}
            </span>
          ))}
          {monthCells(month).map((d, i) => {
            if (!d) return <span key={`blank-${i}`} />;
            const spent = spentByDay.get(d) ?? 0;
            const num = Number(d.slice(8));
            const cls = `cal${d === today ? " today" : ""}${d === selectedDay ? " on" : ""}`;
            const inner = (
              <>
                <span className="num">{num}</span>
                <span className="daily">{spent ? `-${spent.toLocaleString("ko-KR")}` : ""}</span>
              </>
            );
            return d > today ? (
              <span key={d} className={`${cls} later`}>
                {inner}
              </span>
            ) : (
              <Link
                key={d}
                className={cls}
                href={d === selectedDay ? `/?month=${month}#history` : `/?month=${month}&day=${d}#history`}
                aria-current={d === selectedDay ? "date" : undefined}
                aria-label={`${num}일 ${spent ? `순지출 ${won(spent)}` : "지출 없음"}`}
              >
                {inner}
              </Link>
            );
          })}
        </div>

        {selectedDay && (
          <div className="filter">
            <span>
              {dayLabel(selectedDay)} 순지출 <strong>{won(spentByDay.get(selectedDay) ?? 0)}</strong>
            </span>
            <Link href={`/?month=${month}#history`}>전체 보기</Link>
          </div>
        )}

        {txns.length === 0 ? (
          <p className="empty">이 달의 내역이 없어요.</p>
        ) : selectedDay && !byDay.has(selectedDay) ? (
          <p className="empty">이 날은 내역이 없어요.</p>
        ) : (
          [...byDay.entries()]
            .filter(([day]) => !selectedDay || day === selectedDay)
            .map(([day, list]) => (
              <div key={day}>
                <h3 className="date">{dayLabel(day)}</h3>
                <ul className="txns">
                  {list.map((t) => (
                    <TxnItem key={t.id} t={t} />
                  ))}
                </ul>
              </div>
            ))
        )}
        {txns.length >= 1000 && <p className="note">최근 1,000건까지 집계해요.</p>}
      </section>

      <details className="fold">
        <summary>
          학습된 규칙 <span className="count">{ruleRows.length}개</span>
        </summary>
        {ruleRows.length === 0 ? (
          <p className="empty">아직 학습된 규칙이 없어요.</p>
        ) : (
          <ul className="rows">
            {ruleRows.map((r) => (
              <li key={r.id}>
                <span>
                  {r.counterparties?.alias ?? r.cp_key.replace(/^m:/, "")}
                  <small>
                    {categoryLabel(r.category)} · {r.hits}회
                  </small>
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
      </details>

      <details className="fold">
        <summary>설정</summary>
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
            더치페이 의심 최소 금액 (원)
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
      </details>

      <footer>장소 분류 데이터: Kakao Local API</footer>
    </main>
  );
}
