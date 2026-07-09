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
        // orphan 자가복구: convId 는 있는데 서버에 대화가 없으면(예: in-memory DynamoDB
        // 재시드로 소멸) 스테일 → 정리해 빈 상태로 되돌린다(다음 전송이 새 대화를 만든다).
        if (data.conversation === null && (data.messages?.length ?? 0) === 0) {
          window.localStorage.removeItem(STORAGE_KEY);
          setConvId(null);
          return;
        }
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
  }, [messages.length]); // 새 메시지 추가 시에만 스크롤 — 폴링 갱신/스트리밍 중엔 위치 유지

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
      let res = await sendUserMessage(id, text);
      // 스테일 convId(소멸된 대화) → 새 대화를 만들어 1회 재시도(스트리밍 중 "busy" 는 재시도 안 함).
      if (!res.ok && res.code === "gone") {
        window.localStorage.removeItem(STORAGE_KEY);
        const fresh = (await createConversation()).convId;
        setConvId(fresh);
        setMessages([]);
        setConv(null);
        res = await sendUserMessage(fresh, text);
      }
      if (!res.ok) setErr(res.message ?? "Send failed");
      else setInput("");
    } catch {
      setErr("An error occurred while sending.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="panel chat">
      <div className="chat-head">
        <span className="chat-head-icon" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 3l1.6 4.2L18 8.8l-4.4 1.6L12 15l-1.6-4.6L6 8.8l4.4-1.6L12 3z" />
            <path d="M18.5 14.5l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8.8-2z" />
          </svg>
        </span>
        <div className="chat-head-text">
          <div className="chat-head-title">Ask the ops agent</div>
          <div className="chat-head-sub">
            Describe a symptom in plain language — the agent proposes a job you approve below.
          </div>
        </div>
        {messages.length > 0 && (
          <button className="chat-new" onClick={newConversation} disabled={agentBusy}>
            ＋ New conversation
          </button>
        )}
      </div>
      <div className="chat-log">
        {messages.length === 0 ? (
          <div className="chat-empty">
            <div className="chat-examples">
              {[
                "api 5xx is rising, find the cause",
                "prepare a PR to raise the checkout timeout",
                "review the latest terraform plan",
              ].map((ex) => (
                <button
                  key={ex}
                  type="button"
                  className="chat-chip"
                  onClick={() => setInput(ex)}
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        ) : (
          messages.map((m) => (
            <div key={m.seq} className={`chat-msg ${m.role}`}>
              <div className="chat-role">{m.role === "user" ? "You" : "Agent"}</div>
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
        {agentBusy && <div className="chat-typing muted">Agent is responding…</div>}
        <div ref={endRef} />
      </div>

      {conv?.proposed_job_id && (
        <div className="chat-proposed">
          A job has been proposed —{" "}
          <Link href={`/jobs/${conv.proposed_job_id}`} className="mono">
            Approve/reject in the Job Queue →
          </Link>
        </div>
      )}

      <div className="chat-input-row">
        <textarea
          className="chat-input mono"
          rows={2}
          value={input}
          placeholder={agentBusy ? "Waiting for the agent…" : "Type a message… (Enter to send, Shift+Enter for newline)"}
          disabled={sending || agentBusy}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              void send();
            }
          }}
          aria-label="Chat input"
        />
        <button
          className="btn primary"
          disabled={sending || agentBusy || input.trim().length === 0}
          onClick={() => void send()}
        >
          {sending ? "Sending…" : "Send"}
        </button>
      </div>
      {err && <p className="action-msg" style={{ color: "var(--red)" }}>{err}</p>}
    </div>
  );
}
