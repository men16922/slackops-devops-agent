"use client";

import { signIn } from "next-auth/react";

export default function LoginPage() {
  return (
    <main className="login-page">
      <section className="panel login-panel">
        <span className="live-dot" aria-hidden="true" />
        <h1>SlackOps Dashboard</h1>
        <p className="page-sub">
          Sign in with an authorized GitHub account to view and operate the job queue.
        </p>
        <button className="btn primary" onClick={() => void signIn("github", { callbackUrl: "/" })}>
          Sign in with GitHub
        </button>
      </section>
    </main>
  );
}
