-- 바로분류 스키마. Supabase 대시보드 → SQL Editor에 통째로 붙여넣고 Run.
-- 다시 돌려야 하면 맨 아래 "초기화" 블록의 주석을 풀고 먼저 실행한다.

create table if not exists counterparties (
  cp_key text primary key,                        -- 가맹점: "m:정규화이름", 사람: "p:" + sha256 앞 16자
  alias text,                                      -- 사람이면 "상대 #n" 또는 사용자가 붙인 별칭
  type text not null default 'merchant' check (type in ('merchant','person','self')),
  created_at timestamptz not null default now()
);

create table if not exists inbox (
  id bigint generated always as identity primary key,
  raw_text text,                                   -- 처리 후 null로 지운다
  source text not null default 'auto',
  status text not null default 'new' check (status in ('new','done','failed')),
  created_at timestamptz not null default now()
);

create table if not exists transactions (
  id bigint generated always as identity primary key,
  ts timestamptz not null,
  amount integer not null check (amount > 0),
  direction text not null check (direction in ('out','in')),
  method text not null check (method in ('card','transfer')),
  cp_key text references counterparties(cp_key),
  cp_label text,                                   -- 가맹점명 또는 별칭 (사람 실명 금지)
  category text,                                   -- null = 아직 분류 전
  confidence real,
  status text not null default 'auto' check (status in ('auto','pending','confirmed')),
  asked_at timestamptz,
  tg_message_id bigint,
  source text not null default 'tg',
  created_at timestamptz not null default now()
);
create index if not exists transactions_tg_msg on transactions (tg_message_id);
create index if not exists transactions_status on transactions (status, asked_at);

create table if not exists splits (
  id bigint generated always as identity primary key,
  txn_id bigint not null references transactions(id) unique,
  total integer not null,
  n integer not null check (n >= 2),
  my_share integer not null,
  receivable integer not null,
  remaining integer not null,
  status text not null default 'open' check (status in ('open','done')),
  created_at timestamptz not null default now()
);

create table if not exists settlements (
  id bigint generated always as identity primary key,
  split_id bigint not null references splits(id),
  txn_id bigint not null references transactions(id),   -- 정산 입금 거래
  amount integer not null,
  matched_by text not null check (matched_by in ('auto','user')),
  created_at timestamptz not null default now()
);

create table if not exists rules (
  id bigint generated always as identity primary key,
  cp_key text unique references counterparties(cp_key),
  category text not null,
  hits integer not null default 1,
  active boolean not null default false,          -- hits >= 2면 true
  created_at timestamptz not null default now()
);

create table if not exists merchant_cache (
  name text primary key,                           -- 정규화한 가맹점명
  kakao_code text,
  kakao_name text,
  category text,
  confidence real,
  created_at timestamptz not null default now()
);

create table if not exists settings (key text primary key, value text not null);
insert into settings (key, value) values
  ('threshold', '0.7'),
  ('daily_ask_cap', '5'),
  ('digest_hour', '21'),
  ('quiet_start', '23'),
  ('quiet_end', '8'),
  ('split_suspect_min', '30000')
on conflict (key) do nothing;

-- 월별 순지출: 엔빵이면 내 몫만, 계좌 이동(self)·입금 제외
create or replace view monthly_summary as
select to_char(t.ts at time zone 'Asia/Seoul', 'YYYY-MM') as month,
       coalesce(t.category, 'unclassified') as category,
       sum(coalesce(s.my_share, t.amount))::bigint as spent,
       count(*)::int as n
from transactions t
left join splits s on s.txn_id = t.id
where t.direction = 'out' and coalesce(t.category, '') <> 'self'
group by 1, 2;

-- RLS: 전부 켠다. anon은 inbox insert만. 나머지는 service_role(Actions, 대시보드 서버)만 접근
alter table counterparties enable row level security;
alter table inbox          enable row level security;
alter table transactions   enable row level security;
alter table splits         enable row level security;
alter table settlements    enable row level security;
alter table rules          enable row level security;
alter table merchant_cache enable row level security;
alter table settings       enable row level security;

drop policy if exists inbox_insert_only on inbox;
create policy inbox_insert_only on inbox for insert to anon with check (true);

-- 초기화 (필요할 때만 주석 해제)
-- drop view if exists monthly_summary;
-- drop table if exists settlements, splits, rules, merchant_cache, transactions, inbox, counterparties, settings cascade;
