import type { NextAuthOptions } from "next-auth";
import { getServerSession } from "next-auth";
import GitHubProvider from "next-auth/providers/github";

export interface DashboardUser {
  login: string;
}

function configuredLogins(): Set<string> {
  return new Set(
    (process.env.GITHUB_ALLOWED_USERS ?? "")
      .split(",")
      .map((value) => value.trim().toLowerCase())
      .filter(Boolean),
  );
}

export function isAllowedLogin(login: string): boolean {
  return configuredLogins().has(login.trim().toLowerCase());
}

/**
 * Local DynamoDB demos can opt into a synthetic identity. It is deliberately
 * unavailable without both the explicit flag and a local DDB endpoint, so a
 * Vercel deployment cannot accidentally become public.
 */
export function isLocalAuthBypass(): boolean {
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

export const authOptions: NextAuthOptions = {
  providers: [
    GitHubProvider({
      clientId: process.env.AUTH_GITHUB_ID ?? process.env.GITHUB_ID ?? "",
      clientSecret: process.env.AUTH_GITHUB_SECRET ?? process.env.GITHUB_SECRET ?? "",
      authorization: { params: { scope: "read:user" } },
    }),
  ],
  secret: process.env.AUTH_SECRET ?? process.env.NEXTAUTH_SECRET,
  session: { strategy: "jwt", maxAge: 60 * 60 * 8 },
  pages: { signIn: "/login" },
  callbacks: {
    async signIn({ profile }) {
      const login = String((profile as { login?: string } | undefined)?.login ?? "").toLowerCase();
      // The dashboard can enqueue and approve operational jobs: an empty
      // allowlist must deny access rather than admit every GitHub account.
      return login.length > 0 && isAllowedLogin(login);
    },
    async jwt({ token, profile }) {
      const login = (profile as { login?: string } | undefined)?.login;
      if (login) token.name = login;
      return token;
    },
  },
};

export async function getDashboardUser(): Promise<DashboardUser | null> {
  if (isLocalAuthBypass()) return { login: "local-dev" };
  const session = await getServerSession(authOptions);
  const login = session?.user?.name?.trim();
  return login && isAllowedLogin(login) ? { login } : null;
}
