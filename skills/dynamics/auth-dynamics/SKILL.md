---
name: auth-dynamics
description: Get or refresh a Dynamics 365 / Microsoft Dataverse WebAPI bearer access token from local token caches, OpenDataverse, ~/.dynamics, or Azure CLI. Use when a user provides a Dynamics 365 URL and asks for an auth token, bearer token, Authorization header, WebAPI token, token source, token expiry, or reusable token for direct Dataverse WebAPI requests.
---

# Auth Dynamics

Get a bearer token for Dynamics 365 / Dataverse WebAPI requests from the local machine.

Use this skill for authentication and for preparing direct WebAPI calls. For reading records, metadata, WhoAmI, or entity sets, use the `dynamics-webapi` skill. For writes, do not use `dynamics-webapi`; get a token here and make explicit custom WebAPI requests.

## Fast Path

Prefer the Python helper. It uses only the Python standard library.

From PowerShell:

```powershell
python "$HOME\.agents\skills\auth-dynamics\scripts\auth_dynamics.py" https://contoso.crm.dynamics.com
```

From macOS/Linux shells:

```bash
python "$HOME/.agents/skills/auth-dynamics/scripts/auth_dynamics.py" https://contoso.crm.dynamics.com
```

If the skill is installed under Codex's default skill root instead, use `$CODEX_HOME/skills/auth-dynamics/scripts/auth_dynamics.py` or `$HOME/.codex/skills/auth-dynamics/scripts/auth_dynamics.py`.

This prints the normalized Dynamics URL, the token file used, and expiry information. It does not print the access token by default.

To print the raw access token for the caller:

```powershell
python "$HOME\.agents\skills\auth-dynamics\scripts\auth_dynamics.py" https://contoso.crm.dynamics.com --print-token
```

To print a ready-to-use HTTP header:

```powershell
python "$HOME\.agents\skills\auth-dynamics\scripts\auth_dynamics.py" https://contoso.crm.dynamics.com --format header
```

If Azure login must target a specific tenant:

```powershell
python "$HOME\.agents\skills\auth-dynamics\scripts\auth_dynamics.py" --tenant 00000000-0000-0000-0000-000000000000 https://contoso.crm.dynamics.com
```

## Token Resolution

Resolve tokens in this order:

1. `./token.json`, only when it has `accessToken` and is not expired.
2. `~/.OpenDataverse/config.json`, matched by the requested Dynamics URL, then `~/.OpenDataverse/tokens/token-<environmentId>.json`.
3. `~/.dynamics/token.json`, only when it has `accessToken` and is not expired.
4. Azure CLI as the last resort.

The first Dynamics argument may be a host, an org URL, or a WebAPI URL. Normalize all of these to the organization URL:

- `contoso.crm.dynamics.com`
- `https://contoso.crm.dynamics.com`
- `https://contoso.crm.dynamics.com/api/data/v9.2`

## Token Shapes

Azure CLI-shaped token files use:

```json
{
  "accessToken": "<access-token>",
  "expiresOn": "2026-05-11 11:46:39.000000",
  "expires_on": 0,
  "subscription": "",
  "tenant": "",
  "tokenType": "Bearer"
}
```

OpenDataverse token files use:

```json
{
  "accessToken": "<access-token>",
  "refreshToken": "<refresh-token>",
  "expiresAt": 1781874173
}
```

Check expiry using `expiresAt`, then `expires_on`, then `expiresOn`. If no expiry can be read, treat the token as expired.

## OpenDataverse Refresh

When an OpenDataverse token is expired, refresh it with its stored `refreshToken` through the Microsoft Entra v2 token endpoint.

Use:

- public client id: `51f81489-12ee-4a9e-aaae-a2591f45987d`
- grant type: `refresh_token`
- scope: `<normalized-dynamics-url>/user_impersonation offline_access`
- tenant: explicit `--tenant` when provided, otherwise `organizations`

Write the refreshed `accessToken`, replacement `refreshToken`, and `expiresAt` back to the same OpenDataverse token file.

If the refresh token is missing, revoked, invalid, or requires interaction, fall through to `~/.dynamics/token.json` and then Azure CLI.

## Azure CLI Fallback

Use Azure CLI only when no reusable source works:

```powershell
az login --allow-no-subscriptions
az account get-access-token --resource https://contoso.crm.dynamics.com --output json
```

When `--tenant` is supplied, pass it to both Azure CLI commands.

Write Azure CLI output back to `~/.dynamics/token.json` if that file existed but was unusable. Otherwise write it to `./token.json`.

## Using The Token

For direct WebAPI calls, send the token as:

```text
Authorization: Bearer <accessToken>
```

Dataverse WebAPI requests should also include:

```text
Accept: application/json
OData-MaxVersion: 4.0
OData-Version: 4.0
```

Treat access tokens as secrets. Do not print or paste a token unless the user explicitly asks for it or the next command requires it.

## Writing To Dynamics

When the user asks to create, update, delete, associate, disassociate, execute an action, or otherwise change Dataverse data, do not use the `dynamics-webapi` skill. That skill is intentionally read-only and only performs `GET` requests.

Use this workflow instead:

1. Get a bearer token with this skill.
2. Confirm the exact organization URL, entity set, row id or alternate key, payload, and intended operation.
3. Build a custom HTTP request with the appropriate WebAPI method.
4. Prefer a small preflight read when it reduces risk, such as checking that the target row exists or reading the current value before a `PATCH`.
5. Let write failures surface with the full HTTP status and Dataverse error body.

Common Dataverse write request shapes:

```text
POST   /api/data/v9.2/<entity-set>
PATCH  /api/data/v9.2/<entity-set>(<guid>)
DELETE /api/data/v9.2/<entity-set>(<guid>)
POST   /api/data/v9.2/<entity-set>(<guid>)/<navigation-property>/$ref
DELETE /api/data/v9.2/<entity-set>(<guid>)/<navigation-property>(<related-guid>)/$ref
POST   /api/data/v9.2/<action-or-bound-action>
```

Use `Content-Type: application/json; charset=utf-8` for requests with JSON bodies. Use `@odata.bind` values for lookups and relationship binds, for example:

```json
{
  "name": "Contoso",
  "primarycontactid@odata.bind": "/contacts(00000000-0000-0000-0000-000000000000)"
}
```

For updates where overwriting a concurrent change would be risky, use conditional headers such as `If-Match` with an ETag from a prior read. For create-only or update-only upsert behavior, use the Dataverse conditional operation headers instead of relying on a hidden fallback.

Keep write scripts task-specific. Do not add write operations to the read-only `dynamics-webapi` helper just to satisfy one write task.
