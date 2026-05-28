---
name: dynamics-webapi
description: Read-only access to Dynamics 365 WebAPI. Use for querying Dataverse entities, running WhoAmI/health checks, listing entity sets, and reading records. Requires a token.json file with a valid Bearer accessToken.
---

# Dynamics 365 Skill

Read-only WebAPI access to a Dynamics 365 / Dataverse environment.

## Prerequisites

A `token.json` file must exist in **either** the current working directory **or** `~/.dynamics/token.json` with this structure:

```json
{
    "accessToken": "<your-access-token>",
    "expiresIn": "",
    "expires_on": 0,
    "subscription": "",
    "tenant": "",
    "tokenType": "Bearer"
}
```

The `accessToken` is sent as `Authorization: Bearer <accessToken>` on every request. The `expires_on` field (Unix timestamp) is checked and a warning is shown if the token appears expired.

## Fast path

Prefer the Python helper. It uses only the Python standard library, so it avoids `npx`, npm registry checks, package resolution, `tsx` startup, and any network-dependent npm cache behavior.

```bash
python ./scripts/dynamics_api.py https://contoso.crm.dynamics.com whoami
```

If `python` is not on PATH, try `py` on Windows:

```powershell
py .\scripts\dynamics_api.py https://contoso.crm.dynamics.com whoami
```

The TypeScript helper remains available as a fallback when Node tooling is already warm or when you are actively editing the TypeScript version.

## Actions

All actions go through the Python helper script by default. The Dynamics URL is the base organisation URL, e.g. `https://contoso.crm.dynamics.com`.

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
- **Token expiry**: The script warns if `expires_on` is in the past, but still attempts the request.
- **Pagination**: If the response contains `@odata.nextLink`, it is printed at the bottom. Fetch the next page with `get <nextLinkUrl>`.
- **Rate limits**: Dynamics 365 enforces API throttling. For large queries, use `$top` and pagination.
