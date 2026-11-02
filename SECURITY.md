# Security policy

Please report suspected vulnerabilities privately to the repository maintainer rather than
posting exploitable details in a public issue.

## Deployment guidance

- Bind to localhost when the server and BitChord run on the same device.
- For LAN use, restrict port 8787 with the host firewall to trusted devices.
- Do not expose LiChord directly to the public internet. The initial service has no user
  authentication, per-user quotas or TLS termination.
- Do not put provider cookies, account credentials or API tokens in issue reports.
- Stream IDs are provider-prefixed identifiers; arbitrary URLs are not accepted as IDs.
- Keep Python dependencies updated.

LiChord does not store Google account credentials or provider cookies.
