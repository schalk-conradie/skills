---
name: dynamics-webapi
description: Read-only access to Dynamics 365 WebAPI. Use for querying Dataverse entities, running WhoAmI/health checks, listing entity sets, and reading records. Uses token.json when valid and can refresh missing or expired tokens through Azure CLI.
---

# Dynamics 365 Skill

Read-only WebAPI access to a Dynamics 365 / Dataverse environment.

## Prerequisites

A `token.json` file can exist in **either** the current working directory **or** `~/.dynamics/token.json` with this structure:

```json
{
    "accessToken": "<your-access-token>",
    "expiresOn": "2026-05-11 11:46:39.000000",
    "expiresIn": "",
    "expires_on": 0,
    "subscription": "",
    "tenant": "",
    "tokenType": "Bearer"
}
```

The first positional Dynamics argument can be either the host name or the full organisation URL. For example, `contoso.crm.dynamics.com`, `https://contoso.crm.dynamics.com`, and `https://contoso.crm.dynamics.com/api/data/v9.2` are normalized to `https://contoso.crm.dynamics.com`. That normalized URL is used as both the WebAPI base and the Azure CLI token resource.

The `accessToken` is sent as `Authorization: Bearer <accessToken>` on every request. The helper checks `expires_on` (Unix timestamp) first, then falls back to the Azure CLI `expiresOn` timestamp string when present. If neither expiry value can be read, the token is treated as expired and refreshed before making the API request.

If `token.json` is missing, `accessToken` is empty, or the expiry is missing/invalid/in the past, the helper generates a new token with Azure CLI:

1. Runs `az login --allow-no-subscriptions`, optionally with `--tenant <tenant_id_or_domain>`
2. Waits for the browser-based sign-in flow to complete
3. Runs `az account get-access-token --resource <normalized-dynamics-url> --output json`
4. Writes the returned JSON to `token.json`

This is implemented inside the Python and TypeScript helpers rather than shell-profile functions, so it works from PowerShell, zsh, bash, and the Codex shell as long as `az` is on `PATH`.

When a token already exists in `~/.dynamics/token.json`, refreshes are written back to that same file. When no token file exists, the new token is written to `./token.json` in the current working directory.

Azure CLI must be installed and available on `PATH` for automatic token generation.

## Fast path

Prefer the Python helper. It uses only the Python standard library, so it avoids `npx`, npm registry checks, package resolution, `tsx` startup, and any network-dependent npm cache behavior.

```bash
python ./scripts/dynamics_api.py contoso.crm.dynamics.com whoami
```

If `python` is not on PATH, try `py` on Windows:

```powershell
py .\scripts\dynamics_api.py contoso.crm.dynamics.com whoami
```

If Azure login needs a specific tenant, pass it before the Dynamics URL:

```bash
python ./scripts/dynamics_api.py --tenant 00000000-0000-0000-0000-000000000000 contoso.crm.dynamics.com whoami
```

The TypeScript helper remains available as a fallback when Node tooling is already warm or when you are actively editing the TypeScript version.

## Actions

All actions go through the Python helper script by default. The Dynamics argument may be the base organisation URL or just the host name, e.g. `contoso.crm.dynamics.com`.

### WhoAmI — verify authentication

```bash
python ./scripts/dynamics_api.py https://contoso.crm.dynamics.com whoami
```

Returns `UserId`, `BusinessUnitId`, and `OrganizationId`.

### Health Check — full diagnostics

```bash
python ./scripts/dynamics_api.py https://contoso.crm.dynamics.com health
```

Runs three checks:
1. **WhoAmI** — confirms API connectivity and valid credentials
2. **Token info** — shows expiry status, tenant, subscription
3. **Entity Sets** — confirms metadata access

### Read records (GET)

```bash
# Get all accounts (default top from server)
python ./scripts/dynamics_api.py https://contoso.crm.dynamics.com get accounts

# With OData query
python ./scripts/dynamics_api.py https://contoso.crm.dynamics.com get "accounts?\$select=name,accountid&\$top=5"

# Full path
python ./scripts/dynamics_api.py https://contoso.crm.dynamics.com get "api/data/v9.2/accounts?\$top=3"

# Absolute URL
python ./scripts/dynamics_api.py https://contoso.crm.dynamics.com get "https://contoso.crm.dynamics.com/api/data/v9.2/accounts?\$top=3"
```

The script automatically prepends the API base URL (`/api/data/v9.2/`) unless the path starts with `http` or `api/`.

### List entity sets

```bash
python ./scripts/dynamics_api.py https://contoso.crm.dynamics.com list
```

Shows all available OData entity set names and their URLs.

### Entity metadata

```bash
# All entity definitions (summary)
python ./scripts/dynamics_api.py https://contoso.crm.dynamics.com metadata

# Specific entity
python ./scripts/dynamics_api.py https://contoso.crm.dynamics.com metadata account
```

## TypeScript fallback

```bash
npx tsx ./scripts/dynamics-api.ts https://contoso.crm.dynamics.com whoami
```

## OData Query Tips

Common query parameters for `get`:
- `$select=name,accountid` — only return specific fields
- `$top=10` — limit results
- `$filter=name eq 'Contoso'` — filter records
- `$orderby=createdon desc` — sort results
- `$expand=primarycontactid` — expand related records
- `$count=true` — include total count

Remember to escape `$` in shell: use `\$` or wrap the query in single quotes.

## Important Notes

- **Read-only**: This skill only performs GET requests. No create, update, or delete operations.
- **Token refresh**: The script uses an existing valid token, but automatically refreshes when the token is missing, expired, or has an empty `accessToken`.
- **Interactive login**: Token generation may open a browser and wait for the user to complete Azure authentication.
- **Pagination**: If the response contains `@odata.nextLink`, it is printed at the bottom. Fetch the next page with `get <nextLinkUrl>`.
- **Rate limits**: Dynamics 365 enforces API throttling. For large queries, use `$top` and pagination.
