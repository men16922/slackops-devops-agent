#!/usr/bin/env bash
# Lambda 배포 zip 빌드 — app/ 패키지만 담는다(서드파티 의존성 없음; boto3 는 Lambda 런타임 제공,
# alarm 경로는 structlog/mcp 미사용 — alarm_lambda.py 주석 참조). 재현 가능·결정적.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$DIR/../.." && pwd)"
BUILD="$DIR/build"
ZIP="$DIR/alarm-producer.zip"

rm -rf "$BUILD" "$ZIP"
mkdir -p "$BUILD"
cp -r "$ROOT/src/app" "$BUILD/app"
find "$BUILD" -name __pycache__ -type d -prune -exec rm -rf {} +
( cd "$BUILD" && zip -qr "$ZIP" app )
echo "built: $ZIP ($(du -h "$ZIP" | cut -f1))"
