// 탐지 카테고리 카탈로그 — 대시보드 Detections 메뉴의 표시 메타(그룹/라벨/설명).
// 실배선 4개(iam/config/ssm/incident) + roadmap(비활성, 비전 노출). 백엔드 실행 키는
// src/app/commands/detect.py:DETECTION_CATEGORIES 와 일치해야 한다(실배선분).

export interface DetectionCatalogItem {
  category: string;
  group: string;
  label: string;
  description: string;
  roadmap?: boolean;
}

export const DETECTION_CATALOG: DetectionCatalogItem[] = [
  {
    category: "iam",
    group: "Security & Compliance",
    label: "IAM Access Analyzer",
    description: "External / public access findings (free, always has findings).",
  },
  {
    category: "config",
    group: "Security & Compliance",
    label: "AWS Config",
    description:
      "Non-compliant resources by rule. ⚠️ needs the AWS Config recorder enabled (paid) — read is free.",
  },
  {
    category: "incident",
    group: "Operations",
    label: "CloudWatch Alarms",
    description: "Active alarms → suggest a diagnose. Read-only (free).",
  },
  {
    category: "ssm",
    group: "Operations",
    label: "SSM Patch Compliance",
    description: "Instances with missing / failed patches. Read-only (free).",
  },
  // ── roadmap (disabled) — 비전만 노출, 과대주장 금지 ──
  {
    category: "trusted-advisor",
    group: "Cost & Optimization",
    label: "Trusted Advisor",
    description: "Needs Business+ support plan.",
    roadmap: true,
  },
  {
    category: "security-hub",
    group: "Security & Compliance",
    label: "Security Hub",
    description: "Aggregated security posture (paid).",
    roadmap: true,
  },
  {
    category: "guardduty",
    group: "Security & Compliance",
    label: "GuardDuty",
    description: "Threat detection (free trial).",
    roadmap: true,
  },
];

export const DETECTION_GROUPS = [
  "Security & Compliance",
  "Operations",
  "Cost & Optimization",
] as const;
