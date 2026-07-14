"use client";

import { signOut } from "next-auth/react";

export function AuthControls({ login }: { login: string }) {
  return (
    <div className="auth-controls">
      <span className="mono">@{login}</span>
      <button className="auth-signout" onClick={() => void signOut({ callbackUrl: "/login" })}>
        Sign out
      </button>
    </div>
  );
}
