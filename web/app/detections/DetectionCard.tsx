"use client";

// 탐지 카테고리 카드 — ON/OFF 토글 + 모드 + "Scan now". 승인 버튼(ApprovalButtons) 패턴 미러:
// useTransition 으로 server action(setDetectionEnabled/scanNow) 호출. roadmap 항목은 비활성 표시.

import { useState, useTransition } from "react";
import type { DetectionCatalogItem } from "../../lib/detections";
import type { DetectionConfig, DetectionMode } from "../../lib/types";
import { scanNow, setDetectionEnabled } from "../actions";

export function DetectionCard({
  item,
  config,
}: {
  item: DetectionCatalogItem;
  config: DetectionConfig | null;
}) {
  const [enabled, setEnabled] = useState(config?.enabled ?? false);
  const [mode, setMode] = useState<DetectionMode>(config?.mode ?? "on-demand");
  const [pending, startTransition] = useTransition();
  const [msg, setMsg] = useState<string | null>(null);

  if (item.roadmap) {
    return (
      <div className="detect-card roadmap">
        <div className="detect-head">
          <span className="detect-label">{item.label}</span>
          <span className="detect-roadmap">roadmap</span>
        </div>
        <p className="detect-desc">{item.description}</p>
      </div>
    );
  }

  function persist(nextEnabled: boolean, nextMode: DetectionMode) {
    startTransition(async () => {
      const res = await setDetectionEnabled(item.category, nextEnabled, nextMode);
      setMsg(res.ok ? null : (res.message ?? "Failed to save"));
    });
  }

  function handleScan() {
    startTransition(async () => {
      const res = await scanNow(item.category);
      setMsg(res.message ?? (res.ok ? "Scan queued" : "Failed"));
    });
  }

  return (
    <div className="detect-card">
      <div className="detect-head">
        <span className="detect-label">{item.label}</span>
        <label className="detect-toggle">
          <input
            type="checkbox"
            checked={enabled}
            disabled={pending}
            onChange={(e) => {
              setEnabled(e.target.checked);
              persist(e.target.checked, mode);
            }}
          />
          <span>{enabled ? "ON" : "OFF"}</span>
        </label>
      </div>
      <p className="detect-desc">{item.description}</p>
      {enabled && (
        <div className="detect-controls">
          <select
            value={mode}
            disabled={pending}
            onChange={(e) => {
              const next = e.target.value as DetectionMode;
              setMode(next);
              persist(enabled, next);
            }}
          >
            <option value="on-demand">On-demand</option>
            <option value="scheduled">Scheduled</option>
          </select>
          <button className="btn scan" disabled={pending} onClick={handleScan}>
            {pending ? "…" : "Scan now"}
          </button>
        </div>
      )}
      {msg && <p className="action-msg">{msg}</p>}
    </div>
  );
}
