# Managed AWS MCP P3 pilot

This directory is a **manual pilot scaffold**, not an enabled SlackOps feature. It does not alter
`deploy/ec2/user-data.sh`, the SlackOps runtime role, the internal proposal MCP server, or any
currently deployed AWS identity.

## What P3 means

P3 is the organization-expansion path for a team that has one narrowly defined task which cannot
be expressed with a fixed SlackOps read adapter. It is deliberately separate from the default
runtime:

| Boundary | SlackOps runtime | P3 managed AWS MCP pilot |
| --- | --- | --- |
| Account | `runtimeAccountId` in `pilot-boundary.json` | a different `pilotAccountId` |
| Identity | bootstrap, runtime, internal-MCP, audit roles | `slackops-managed-aws-mcp-pilot-role` only |
| Capability | fixed command adapters; generic AWS MCP absent | three CloudWatch Logs read actions only |
| Evidence | SlackOps boundary audit sink | CloudTrail `AwsMcpEvent` records |
| Network | existing local egress proxy | verify selected-server VPC endpoint support before requiring it |

The example role policy allows only `DescribeLogStreams`, `GetLogEvents`, and `FilterLogEvents`
under the approved log-group prefix. The allow statement requires both AWS-managed-MCP context
keys; the policy also explicitly denies mutations. Do not attach additional policies, permissions
boundaries, or a trust policy that makes a SlackOps runtime role a pilot principal.

## Operator sequence

1. Copy `pilot-boundary.json` values into the change ticket. Set different, real runtime and pilot
   account IDs, one region, and a review-approved log-group prefix.
2. Create the pilot role in the **pilot account** with a trust policy for the separately approved
   pilot identity. Do not reuse any role named in `forbiddenRuntimeRoles`.
3. Render `pilot-role-policy.json` by replacing its three placeholders. Attach only that policy
   (and organization controls that are no broader).
4. Enable a CloudTrail trail or CloudTrail Lake event data store that captures AWS MCP Server data
   events. Run one harmless approved read, then adapt and run
   `cloudtrail-lake-violations.sql`. The result must be empty; retain the query ID and the allowed
   event as the change evidence.
5. Before making a VPC endpoint mandatory, confirm that the selected managed MCP server supports
   it in the target Region. This scaffold makes no claim that an endpoint is available today.
6. Security owner reviews the event identity, `readOnly=true`, recipient account, Region, MCP
   server name, and requested resource. Only then can one additional read action be proposed.

## Stop conditions

- Same runtime and pilot account ID, or any SlackOps runtime role in the pilot trust relationship.
- A CloudTrail event that is not `AwsMcpEvent`, has a different recipient account or Region, a
  caller outside the pilot role, `readOnly=false`, or an unexpected `aws-mcp.*` server.
- Any request for write, IAM, STS role switching, or an unapproved log-group prefix.

The query is a review template rather than a deployment command: CloudTrail Lake event data store
schemas and IDs are account-specific. Test its field syntax against one retained pilot event before
using it as an automated guard.
