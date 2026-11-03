// 카테고리 아이콘. 외부 이미지나 로고 없이 직접 그린 단순한 선 그림만 쓴다.
const GLYPHS: Record<string, React.ReactNode> = {
  food: (
    <>
      <path d="M5 12h14a7 7 0 0 1-14 0Z" />
      <path d="M9 8c0-1.5 1-1.5 1-3M14 8c0-1.5 1-1.5 1-3" />
    </>
  ),
  cafe: (
    <>
      <path d="M6 9h10v6a4 4 0 0 1-4 4h-2a4 4 0 0 1-4-4V9Z" />
      <path d="M16 11h1.5a2 2 0 0 1 0 4H16M9 6V4.5M13 6V4.5" />
    </>
  ),
  mart: (
    <>
      <path d="M5 10v9h14v-9" />
      <path d="M4 10l1.5-5h13L20 10a2.7 2.7 0 0 1-5.3 0 2.7 2.7 0 0 1-5.4 0A2.7 2.7 0 0 1 4 10Z" />
    </>
  ),
  transport: (
    <>
      <rect x="5" y="5" width="14" height="12" rx="3" />
      <path d="M5 12h14M8 17v2M16 17v2" />
    </>
  ),
  shopping: (
    <>
      <path d="M6 9h12l1 11H5L6 9Z" />
      <path d="M9 11V7a3 3 0 0 1 6 0v4" />
    </>
  ),
  living: (
    <>
      <path d="M4 12l8-7 8 7" />
      <path d="M6.5 10.5V19h11v-8.5M10 19v-5h4v5" />
    </>
  ),
  edu: (
    <>
      <path d="M12 7c-2-1.5-4.5-2-7-2v13c2.5 0 5 .5 7 2 2-1.5 4.5-2 7-2V5c-2.5 0-5 .5-7 2Z" />
      <path d="M12 7v13" />
    </>
  ),
  culture: (
    <>
      <path d="M12 4.5l2.2 4.6 5 .7-3.6 3.5.9 5-4.5-2.4-4.5 2.4.9-5L4.8 9.8l5-.7L12 4.5Z" />
    </>
  ),
  health: <path d="M12 6v12M6 12h12" />,
  gift: (
    <>
      <rect x="5" y="10" width="14" height="10" rx="1.5" />
      <path d="M4 10h16M12 10v10M12 10c-4 0-5-4-2.5-4.5S12 10 12 10Zm0 0c4 0 5-4 2.5-4.5S12 10 12 10Z" />
    </>
  ),
  transfer: <path d="M5 9h13l-3.5-3.5M19 15H6l3.5 3.5" />,
  self: <path d="M5 9h13l-3.5-3.5M19 15H6l3.5 3.5" />,
  etc: <path d="M6.5 12h.01M12 12h.01M17.5 12h.01" />,
  income: <path d="M12 5v14M6 13l6 6 6-6" />,
  settlement: <path d="M5 12.5l4.5 4.5L19 7.5" />,
};

export function CategoryIcon({ code }: { code: string | null | undefined }) {
  const key = code && GLYPHS[code] ? code : "etc";
  return (
    <span className={`icon cat-${key}`} aria-hidden="true">
      <svg
        viewBox="0 0 24 24"
        width="26"
        height="26"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {GLYPHS[key]}
      </svg>
    </span>
  );
}
