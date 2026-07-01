# PeekXD Safety Policy

## MCP safety bypass allowlist

The MCP server defaults to safety middleware enabled. Startup does not bypass `SafetyMiddleware` unless all of the following are true:

1. `PEEKXD_SAFETY_MCP=1` is present in the environment.
2. `mcp.trusted_bootstrap` is truthy in configuration.
3. The configured transport is trusted local bootstrap scope:
   - `stdio`, or
   - a non-stdio transport bound to `localhost`, `127.0.0.1`, `::1`, or an empty host.

Legacy values such as `PEEKXD_SAFETY_MCP=0` are not allowlisted and do not enable bypass. This avoids accidental safety disablement by scripts that interpret `0` as a literal safety-related toggle.

When bypass is disabled, MCP tools are registered through `SafetyMiddleware` and continue to emit zone and audit metadata. When bypass is enabled, tools are registered directly for backwards-compatible local bootstrap flows only.

## Startup evidence

Every MCP server creation records a startup policy evidence entry before tools are registered. The entry includes:

- `safety_bypass_enabled`
- `safety_bypass_source`
- `safety_bypass_env`
- `trusted_bootstrap`
- `transport`
- `host`

The same resolved state is also emitted to the `peekxd.mcp_server.server` logger. If bypass is active, startup emits an additional warning that the bypass is intended only for local operator-controlled bootstrap.
