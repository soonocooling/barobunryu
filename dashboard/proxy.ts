import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// 모든 경로에 Basic 인증을 건다. 사용자 이름은 무엇이든 허용하고 비밀번호만 본다.
// DASH_PASSWORD가 비어 있으면 전부 401이다(실수로 열리는 것 방지).

function unauthorized(): NextResponse {
  return new NextResponse("인증이 필요해요.", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="dashboard"' },
  });
}

function safeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export function proxy(request: NextRequest) {
  const expected = process.env.DASH_PASSWORD;
  if (!expected) return unauthorized();

  const header = request.headers.get("authorization") ?? "";
  const [scheme, encoded] = header.split(" ");
  if (scheme?.toLowerCase() !== "basic" || !encoded) return unauthorized();

  let decoded: string;
  try {
    const bytes = Uint8Array.from(atob(encoded), (c) => c.charCodeAt(0));
    decoded = new TextDecoder().decode(bytes);
  } catch {
    return unauthorized();
  }
  const password = decoded.slice(decoded.indexOf(":") + 1);
  if (decoded.indexOf(":") < 0 || !safeEqual(password, expected)) return unauthorized();

  return NextResponse.next();
}
