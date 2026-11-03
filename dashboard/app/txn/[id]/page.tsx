import Link from "next/link";
import { notFound } from "next/navigation";

import { categoryLabel, getTxn, pickableCategories, settledAmount, type SplitDetail } from "@/lib/db";
import { changeCategory, removeDutch, saveDutch } from "../../actions";
import { CategoryIcon } from "../../icons";

export const dynamic = "force-dynamic";

const won = (n: number) => `${n.toLocaleString("ko-KR")}원`;

const MESSAGES: Record<string, { text: string; err?: boolean }> = {
  category: { text: "카테고리를 바꿨어요." },
  dutch: { text: "더치페이를 저장했어요." },
  undutch: { text: "더치페이를 해제했어요." },
  locked: { text: "이 거래의 카테고리는 바꿀 수 없어요.", err: true },
  invalid: { text: "인원(2~20명)이나 내 몫 금액을 확인해 주세요.", err: true },
  settled: { text: "이미 받은 돈 기록과 맞지 않아 바꿀 수 없어요.", err: true },
  fail: { text: "저장하지 못했어요. 잠시 뒤 다시 시도해 주세요.", err: true },
};

function fullDate(iso: string): string {
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "long",
    day: "numeric",
    weekday: "long",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(iso));
}

export default async function TxnPage(props: PageProps<"/txn/[id]">) {
  const { id: rawId } = await props.params;
  const params = await props.searchParams;
  const txn = await getTxn(Number(rawId));
  if (!txn) notFound();

  const msg = typeof params.msg === "string" ? MESSAGES[params.msg] : undefined;
  const split: SplitDetail | null = (Array.isArray(txn.splits) ? txn.splits[0] : txn.splits) ?? null;
  const settled = split ? await settledAmount(split.id) : 0;
  const incoming = txn.direction === "in";
  const locked = txn.category === "settlement";
  const month = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Seoul",
    year: "numeric",
    month: "2-digit",
  }).format(new Date(txn.ts));

  return (
    <main>
      <header className="top detail-top">
        <Link href={`/?month=${month}#history`} className="back" aria-label="내역으로 돌아가기" />
        <span>상세 내역</span>
      </header>

      {msg && <div className={`notice ${msg.err ? "err" : "ok"}`}>{msg.text}</div>}

      <section className="plain">
        <div className="hero-name">
          <CategoryIcon code={txn.category} />
          <span>{txn.cp_label ?? "이름 없음"}</span>
        </div>
        <p className={`hero-amount${incoming ? " in" : ""}`}>
          {incoming ? "+" : "-"}
          {won(split?.my_share ?? txn.amount)}
        </p>
        {split && <p className="note">결제 금액 {won(txn.amount)} 중 내 몫이에요.</p>}
        <dl className="facts">
          <div>
            <dt>거래 일시</dt>
            <dd>{fullDate(txn.ts)}</dd>
          </div>
          <div>
            <dt>구분</dt>
            <dd>
              {incoming ? "입금" : "출금"} · {txn.method === "transfer" ? "이체" : "카드"}
            </dd>
          </div>
          <div>
            <dt>카테고리</dt>
            <dd className="accent">{categoryLabel(txn.category)}</dd>
          </div>
        </dl>
      </section>

      {!incoming && (
        <section className="plain">
          <p className="label">더치페이</p>
          {split ? (
            <dl className="facts">
              <div>
                <dt>받을 돈</dt>
                <dd>{won(split.receivable)}</dd>
              </div>
              <div>
                <dt>받은 돈</dt>
                <dd>{won(settled)}</dd>
              </div>
              <div>
                <dt>남은 돈</dt>
                <dd className="accent">{won(split.remaining)}</dd>
              </div>
            </dl>
          ) : (
            <p className="empty">여럿이 나눠 낸 거래라면 인원을 입력해 주세요.</p>
          )}
          <form action={saveDutch} className="settings dutch">
            <input type="hidden" name="id" value={txn.id} />
            <label>
              인원 (2~20명)
              <input type="number" name="n" min="2" max="20" step="1" defaultValue={split?.n ?? ""} />
            </label>
            <label>
              내 몫 (원)
              <input
                type="number"
                name="my_share"
                min="1"
                max={txn.amount - 1}
                step="1"
                defaultValue={split?.my_share ?? ""}
              />
              <span className="hint">비워 두면 인원으로 똑같이 나눠요.</span>
            </label>
            <button type="submit">{split ? "더치페이 수정" : "더치페이로 전환"}</button>
          </form>
          {split && settled === 0 && (
            <form action={removeDutch} className="undo">
              <input type="hidden" name="id" value={txn.id} />
              <button type="submit" className="ghost">
                더치페이 해제
              </button>
            </form>
          )}
        </section>
      )}

      <section className="plain">
        <p className="label">카테고리 설정</p>
        {locked ? (
          <p className="empty">더치페이 정산으로 연결된 입금이라 바꿀 수 없어요.</p>
        ) : (
          <form action={changeCategory} className="picker">
            <input type="hidden" name="id" value={txn.id} />
            {pickableCategories(txn.direction).map((c) => (
              <button
                key={c.code}
                type="submit"
                name="category"
                value={c.code}
                className={c.code === txn.category ? "pick on" : "pick"}
                aria-current={c.code === txn.category}
              >
                <CategoryIcon code={c.code} />
                <span>{c.label}</span>
              </button>
            ))}
          </form>
        )}
        <p className="note">바꾼 분류는 규칙으로 학습돼요. 텔레그램의 이전 메시지는 그대로 남아요.</p>
      </section>
    </main>
  );
}
