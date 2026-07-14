import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import { getToken } from "next-auth/jwt";

function localDemoBypass(): boolean {
  if (process.env.AUTH_BYPASS_FOR_LOCAL_DEVELOPMENT !== "true") return false;
  const endpoint = process.env.DDB_ENDPOINT;
  if (!endpoint) return false;
  try {
    return new Set(["localhost", "127.0.0.1", "dynamodb-local"]).has(
      new URL(endpoint).hostname,
    );
  } catch {
    return false;
  }
}

export async function middleware(request: NextRequest) {
  if (localDemoBypass() || request.nextUrl.pathname === "/login") {
    return NextResponse.next();
  }
  const token = await getToken({
    req: request,
    secret: process.env.AUTH_SECRET ?? process.env.NEXTAUTH_SECRET,
  });
  const allowedLogins = new Set(
    (process.env.GITHUB_ALLOWED_USERS ?? "")
      .split(",")
      .map((value) => value.trim().toLowerCase())
      .filter(Boolean),
  );
  if (token?.name && allowedLogins.has(String(token.name).toLowerCase())) {
    return NextResponse.next();
  }

  const login = new URL("/login", request.url);
  login.searchParams.set("callbackUrl", request.nextUrl.pathname);
  return NextResponse.redirect(login);
}

export const config = {
  matcher: ["/((?!api/auth|_next/static|_next/image|favicon.ico).*)"],
};
