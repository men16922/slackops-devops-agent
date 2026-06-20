// Detections 메뉴 — 거버넌스 탐지 카테고리 ON/OFF + "Scan now". 토글은 DynamoDB
// 단일테이블(CONFIG#detections)에 저장 → 테이블이 탐지 커버리지의 컨트롤 플레인.

import { DETECTION_CATALOG, DETECTION_GROUPS } from "../../lib/detections";
import { getDetectionConfigs } from "../../lib/ddb";
import { DetectionCard } from "./DetectionCard";

export const dynamic = "force-dynamic";

export default async function DetectionsPage() {
  const configs = await getDetectionConfigs();
  const byCategory = new Map(configs.map((c) => [c.category, c]));

  return (
    <>
      <h1>Detections</h1>
      <p className="page-sub">
        Toggle governance detection categories. Enabled categories scan on-demand or
        on a schedule; findings land in the job queue (read-only AWS, human-gated
        remediation). Real findings require cloud credentials (EC2 + IAM).
      </p>
      {DETECTION_GROUPS.map((group) => {
        const items = DETECTION_CATALOG.filter((i) => i.group === group);
        if (items.length === 0) return null;
        return (
          <section key={group} className="detect-group">
            <h2>{group}</h2>
            <div className="detect-grid">
              {items.map((item) => (
                <DetectionCard
                  key={item.category}
                  item={item}
                  config={byCategory.get(item.category) ?? null}
                />
              ))}
            </div>
          </section>
        );
      })}
    </>
  );
}
