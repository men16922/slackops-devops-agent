"use client";

// 대화형 producer — 자유 텍스트로 에이전트(Claude)와 대화하고, 에이전트가 구체 작업이
// 필요하다 판단하면 propose_job 으로 Job Queue 에 제안(승인/거절). 입력은 Claude 에 직접
// 가지 않고 DynamoDB 대화 버스에 적재 → 에이전트(chat_agent)가 폴링·sanitizer 격리 후 처리.
// 스트리밍은 ~800ms 폴링으로 자라나는 assistant 메시지를 렌더(에이전트 인바운드 없음).

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import type { ChatMessage, Conversation } from "../lib/types";
import { Markdown } from "./Markdown";
import { createConversation, sendUserMessage } from "./chat-actions";

const POLL_MS = 800;

export function Chat() {
  const [convId, setConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [conv, setConv] = useState<Conversation | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const endRef = useRef<HTMLDivElement | null>(null);

  const STORAGE_KEY = "slackops_conv";

  // 새로고침해도 대화 유지 — convId 를 localStorage 에서 복원/저장.
  useEffect(() => {
    const saved = window.localStorage.getItem(STORAGE_KEY);
    if (saved) setConvId(saved);
  }, []);
  useEffect(() => {
    if (convId) window.localStorage.setItem(STORAGE_KEY, convId);
  }, [convId]);

  function newConversation() {
    window.localStorage.removeItem(STORAGE_KEY);
    setConvId(null);
    setMessages([]);
    setConv(null);
    setErr(null);
  }

  // convId 가 생기면 메시지/상태를 주기적으로 폴링.
  useEffect(() => {
    if (!convId) return;
    let stop = false;
    async function tick() {
      try {
        const r = await fetch(`/api/chat/${convId}`, { cache: "no-store" });
        if (!r.ok || stop) return;
        const data = (await r.json()) as {
          conversation: Conversation | null;
          messages: ChatMessage[];
        };
        if (stop) return;
        setMessages(data.messages ?? []);
        setConv(data.conversation ?? null);
      } catch {
        /* 폴링 실패는 다음 tick 에서 복구 */
      }
    }
    void tick();
    const h = setInterval(tick, POLL_MS);
    return () => {
      stop = true;
      clearInterval(h);
    };
  }, [convId]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const agentBusy = conv?.status === "awaiting_agent" || conv?.status === "streaming";

  async function send() {
    const text = input.trim();
    if (!text || sending || agentBusy) return;
    setErr(null);
    setSending(true);
    try {
      let id = convId;
      if (!id) {
        id = (await createConversation()).convId;
        setConvId(id);
      }
      const res = await sendUserMessage(id, text);
      if (!res.ok) setErr(res.message ?? "전송 실패");
      else setInput("");
    } catch {
      setErr("전송 중 오류가 발생했습니다.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="panel chat">
      {messages.length > 0 && (
        <div className="chat-header">
          <button className="chat-new" onClick={newConversation} disabled={agentBusy}>
            ＋ 새 대화
          </button>
        </div>
      )}
      <div className="chat-log">
        {messages.length === 0 ? (
          <p className="chat-empty muted">
            운영 에이전트와 대화하세요. 예: <span className="mono">api 5xx 늘었어, 원인 봐줘</span> ·{" "}
            <span className="mono">checkout 타임아웃 올리는 PR 준비해줘</span>
            <br />
            에이전트가 필요하다 판단하면 작업을 제안하고, 아래 Job Queue 에서 승인/거절합니다.
          </p>
        ) : (
          messages.map((m) => (
            <div key={m.seq} className={`chat-msg ${m.role}`}>
              <div className="chat-role">{m.role === "user" ? "🧑 you" : "🤖 agent"}</div>
              <div className="chat-bubble">
                {m.role === "assistant" ? (
                  m.content ? (
                    <Markdown text={m.content} />
                  ) : (
                    <span className="muted">…</span>
                  )
                ) : (
                  <span className="chat-user-text">{m.content}</span>
                )}
              </div>
            </div>
          ))
        )}
        {agentBusy && <div className="chat-typing muted">에이전트 응답 중…</div>}
        <div ref={endRef} />
      </div>

      {conv?.proposed_job_id && (
        <div className="chat-proposed">
          🤖 작업이 제안되었습니다 —{" "}
          <Link href={`/jobs/${conv.proposed_job_id}`} className="mono">
            Job Queue 에서 승인/거절 →
          </Link>
        </div>
      )}

      <div className="chat-input-row">
        <textarea
          className="chat-input mono"
          rows={2}
          value={input}
          placeholder={agentBusy ? "에이전트 응답을 기다리는 중…" : "메시지를 입력…(Enter 전송, Shift+Enter 줄바꿈)"}
          disabled={sending || agentBusy}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
          aria-label="대화 입력"
        />
        <button
          className="btn approve"
          disabled={sending || agentBusy || input.trim().length === 0}
          onClick={() => void send()}
        >
          {sending ? "전송 중…" : "Send"}
        </button>
      </div>
      {err && <p className="action-msg" style={{ color: "var(--red)" }}>{err}</p>}
    </div>
  );
}
