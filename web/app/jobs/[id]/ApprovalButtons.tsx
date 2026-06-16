"use client";

import { useState, useTransition } from "react";
import { approveJob, rejectJob, type ActionResult } from "../../actions";

export function ApprovalButtons({ id }: { id: string }) {
  const [pending, startTransition] = useTransition();
  const [msg, setMsg] = useState<string | null>(null);

  function run(action: (id: string) => Promise<ActionResult>) {
    setMsg(null);
    startTransition(async () => {
      const res = await action(id);
      if (!res.ok && res.message) setMsg(res.message);
    });
  }

  return (
    <div>
      <div className="btnrow">
        <button
          className="btn approve"
          disabled={pending}
          onClick={() => run(approveJob)}
        >
          {pending ? "처리 중…" : "Approve"}
        </button>
        <button
          className="btn reject"
          disabled={pending}
          onClick={() => run(rejectJob)}
        >
          Reject
        </button>
      </div>
      {msg && <p className="action-msg">{msg}</p>}
    </div>
  );
}
