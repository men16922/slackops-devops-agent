-- P3 manual evidence query. Replace __EVENT_DATA_STORE_ID__, __PILOT_ACCOUNT_ID__,
-- __PILOT_REGION__, and __PILOT_ROLE_NAME__ before running in CloudTrail Lake.
-- Empty result is the acceptance criterion. Review any returned row before expanding scope.
SELECT
  eventTime,
  eventSource,
  eventName,
  awsRegion,
  recipientAccountId,
  userIdentity.arn AS callerArn,
  readOnly,
  mcpEventDetails.mcpServerName AS mcpServerName,
  mcpEventDetails.sessionId AS mcpSessionId
FROM __EVENT_DATA_STORE_ID__
WHERE eventType = 'AwsMcpEvent'
  AND (
    recipientAccountId <> '__PILOT_ACCOUNT_ID__'
    OR awsRegion <> '__PILOT_REGION__'
    OR userIdentity.arn NOT LIKE '%:assumed-role/__PILOT_ROLE_NAME__/%'
    OR readOnly <> true
    OR eventSource NOT LIKE 'aws-mcp.%'
  )
ORDER BY eventTime DESC;
