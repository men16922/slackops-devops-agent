#!/usr/bin/env bash
# EC2 c7i.large 기동 — Instance Profile 부착, 인바운드 포트 없음(아웃바운드 전용 SG).
set -euo pipefail

PROFILE_NAME="${PROFILE_NAME:-slackops-devops-agent-profile}"
INSTANCE_TYPE="${INSTANCE_TYPE:-c7i.large}"
TAG_NAME="${TAG_NAME:-slackops-devops-agent}"
DIR="$(cd "$(dirname "$0")" && pwd)"

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
  --user-data "file://$DIR/user-data.sh" \
  --tag-specifications \
    "ResourceType=instance,Tags=[{Key=Name,Value=$TAG_NAME},{Key=Project,Value=slackops-devops-agent}]" \
  --query 'Instances[0].InstanceId' --output text
