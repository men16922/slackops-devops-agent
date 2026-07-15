#!/usr/bin/env bash
# EC2 c7i.large 기동 — Instance Profile 부착, 인바운드 포트 없음(아웃바운드 전용 SG).
set -euo pipefail

PROFILE_NAME="${PROFILE_NAME:-slackops-devops-agent-profile}"
# Claude Code headless 는 로컬 LLM 을 돌리지 않는다(추론은 원격 API) — EC2 는 오케스트레이터.
# bursty I/O 워크로드라 burstable t3.medium(2vCPU/4GB)이 적합·c7i.large 대비 ~53% 저렴.
INSTANCE_TYPE="${INSTANCE_TYPE:-t3.medium}"
TAG_NAME="${TAG_NAME:-slackops-devops-agent}"
DIR="$(cd "$(dirname "$0")" && pwd)"
SOURCE_ARCHIVE_URL="${SOURCE_ARCHIVE_URL:-}"
SOURCE_ARCHIVE_SHA256="${SOURCE_ARCHIVE_SHA256:-}"
USER_DATA="$DIR/user-data.sh"
TEMP_USER_DATA=""

cleanup() {
  [[ -z "$TEMP_USER_DATA" ]] || rm -f "$TEMP_USER_DATA"
}
trap cleanup EXIT

escape_sed_replacement() {
  printf '%s' "$1" | sed 's/[\\&|]/\\&/g'
}

if [[ -n "$SOURCE_ARCHIVE_URL" ]]; then
  [[ -n "$SOURCE_ARCHIVE_SHA256" ]] || {
    echo "SOURCE_ARCHIVE_SHA256 is required when SOURCE_ARCHIVE_URL is set" >&2
    exit 2
  }
  TEMP_USER_DATA="$(mktemp)"
  sed \
    -e "s|^SOURCE_ARCHIVE_URL=\"\"$|SOURCE_ARCHIVE_URL=\"$(escape_sed_replacement "$SOURCE_ARCHIVE_URL")\"|" \
    -e "s|^SOURCE_ARCHIVE_SHA256=\"\"$|SOURCE_ARCHIVE_SHA256=\"$(escape_sed_replacement "$SOURCE_ARCHIVE_SHA256")\"|" \
    "$USER_DATA" > "$TEMP_USER_DATA"
  USER_DATA="$TEMP_USER_DATA"
fi

# 최신 AL2023 AMI
AMI_ID="$(aws ssm get-parameter \
  --name /aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64 \
  --query Parameter.Value --output text)"

# 인바운드 규칙 없는 보안 그룹(없으면 생성) — Socket Mode 는 아웃바운드만 필요.
VPC_ID="${VPC_ID:-$(aws ec2 describe-vpcs --filters Name=is-default,Values=true \
  --query 'Vpcs[0].VpcId' --output text)}"
SG_ID="$(aws ec2 describe-security-groups \
  --filters Name=group-name,Values="$TAG_NAME-sg" Name=vpc-id,Values="$VPC_ID" \
  --query 'SecurityGroups[0].GroupId' --output text 2>/dev/null || echo None)"
if [ "$SG_ID" = "None" ]; then
  SG_ID="$(aws ec2 create-security-group \
    --group-name "$TAG_NAME-sg" --vpc-id "$VPC_ID" \
    --description "slackops-devops-agent: no inbound, outbound only" \
    --query GroupId --output text)"
fi

aws ec2 run-instances \
  --image-id "$AMI_ID" \
  --instance-type "$INSTANCE_TYPE" \
  --iam-instance-profile "Name=$PROFILE_NAME" \
  --security-group-ids "$SG_ID" \
  --metadata-options "HttpTokens=required,HttpEndpoint=enabled" \
  --user-data "file://$USER_DATA" \
  --tag-specifications \
    "ResourceType=instance,Tags=[{Key=Name,Value=$TAG_NAME},{Key=Project,Value=slackops-devops-agent}]" \
  --query 'Instances[0].InstanceId' --output text
