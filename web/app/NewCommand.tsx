"use client";

// 웹 producer 입력 — 명령 선택 + 인자칸. 자유 텍스트를 Claude 에 직접 보내지 않고
// 알려진 명령으로 구조화해 큐에 적재(enqueueJob, default deny). 실행은 worker 담당.

import { useState, useTransition } from "react";
import { enqueueJob } from "./actions";

interface CommandSpec {
  value: string;
  label: string;
  placeholder: string;
  argsRequired: boolean;
}

const COMMANDS: CommandSpec[] = [
  { value: "logs", label: "logs — CloudWatch 로그 조회+분석", placeholder: "서비스명 (예: api)", argsRequired: true },
  { value: "diagnose", label: "diagnose — 다중 소스 종합 진단", placeholder: "서비스명 (예: api)", argsRequired: true },
  { value: "tf-review", label: "tf-review — terraform plan 리뷰", placeholder: "(인자 불필요)", argsRequired: false },
  { value: "pr", label: "pr — branch→수정→test→PR", placeholder: "변경 설명 (예: nginx timeout 30s 로 상향)", argsRequired: true },
  { value: "ping", label: "ping — 헬스체크", placeholder: "(인자 불필요)", argsRequired: false },
];

export function NewCommand() {
  const [command, setCommand] = useState<string>(COMMANDS[0].value);
  const [args, setArgs] = useState("");
  const [pending, startTransition] = useTransition();
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  const spec = COMMANDS.find((c) => c.value === command) ?? COMMANDS[0];

  function submit() {
    setMsg(null);
    startTransition(async () => {
      const res = await enqueueJob(command, args);
      setMsg({ ok: res.ok, text: res.message ?? (res.ok ? "큐에 추가됨" : "실패") });
      if (res.ok) setArgs("");
    });
  }

  return (
    <div className="panel composer">
      <div className="composer-row">
        <select
          className="composer-cmd mono"
          value={command}
          onChange={(e) => setCommand(e.target.value)}
          disabled={pending}
          aria-label="명령 선택"
        >
          {COMMANDS.map((c) => (
            <option key={c.value} value={c.value}>
              {c.label}
            </option>
          ))}
        </select>
        <input
          className="composer-args mono"
          type="text"
          value={args}
          placeholder={spec.placeholder}
          disabled={pending || !spec.argsRequired}
          onChange={(e) => setArgs(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") submit();
          }}
          aria-label="명령 인자"
        />
        <button className="btn approve" disabled={pending} onClick={submit}>
          {pending ? "보내는 중…" : "Send"}
        </button>
      </div>
      <p className="composer-hint muted">
        명령은 큐(<span className="mono">status=pending, source=web</span>)에 적재됩니다 — 실행은 worker 담당.
      </p>
      {msg && (
        <p className="action-msg" style={{ color: msg.ok ? "var(--green)" : "var(--red)" }}>
          {msg.text}
        </p>
      )}
    </div>
  );
}
