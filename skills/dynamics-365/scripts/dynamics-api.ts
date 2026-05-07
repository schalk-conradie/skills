#!/usr/bin/env npx tsx
/**
 * Dynamics 365 WebAPI helper — read-only access
 *
 * Usage:
 *   npx tsx dynamics-api.ts <dynamics-url> whoami
 *   npx tsx dynamics-api.ts <dynamics-url> health
 *   npx tsx dynamics-api.ts <dynamics-url> get <path-or-query>
 *   npx tsx dynamics-api.ts <dynamics-url> list
 *   npx tsx dynamics-api.ts <dynamics-url> metadata [entity-logical-name]
 */

import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { homedir } from "node:os";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TokenFile {
  accessToken: string;
  expiresIn?: string;
  expires_on?: number;
  subscription?: string;
  tenant?: string;
  tokenType?: string;
}

// ---------------------------------------------------------------------------
// Token loading
// ---------------------------------------------------------------------------

function findTokenFile(): string {
  const cwd = join(process.cwd(), "token.json");
  const home = join(homedir(), ".dynamics", "token.json");
  if (existsSync(cwd)) return cwd;
  if (existsSync(home)) return home;
  console.error("ERROR: token.json not found in current directory or ~/.dynamics/");
  console.error("Expected format:");
  console.error(JSON.stringify({
    accessToken: "...",
    expiresIn: "",
    expires_on: 0,
    subscription: "",
    tenant: "",
    tokenType: "Bearer",
  }, null, 4));
  process.exit(1);
}

function loadToken(path: string): TokenFile {
  try {
    return JSON.parse(readFileSync(path, "utf-8"));
  } catch (err) {
    console.error(`ERROR: Failed to parse ${path}: ${err}`);
    process.exit(1);
  }
}

function checkExpiry(token: TokenFile): void {
  if (!token.expires_on || token.expires_on === 0) {
    console.log("  Expiry: Not set");
    return;
  }
  const now = Math.floor(Date.now() / 1000);
  const remaining = token.expires_on - now;
  if (remaining > 0) {
    const date = new Date(token.expires_on * 1000).toISOString().replace("T", " ").slice(0, 19);
    console.log(`  Expiry: Valid (${remaining}s remaining, expires ${date})`);
  } else {
    const date = new Date(token.expires_on * 1000).toISOString().replace("T", " ").slice(0, 19);
    console.log(`  Expired: ${Math.abs(remaining)}s ago (${date})`);
  }
}

// ---------------------------------------------------------------------------
// HTTP helper
// ---------------------------------------------------------------------------

async function apiGet(url: string, accessToken: string): Promise<unknown> {
  const res = await fetch(url, {
    method: "GET",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "OData-MaxVersion": "4.0",
      "OData-Version": "4.0",
      Accept: "application/json",
      "Content-Type": "application/json; charset=utf-8",
    },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`HTTP ${res.status} ${res.statusText}${body ? ": " + body.slice(0, 500) : ""}`);
  }
  return res.json();
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

async function whoami(baseUrl: string, accessToken: string): Promise<void> {
  console.log("=== Dynamics 365 WhoAmI ===");
  console.log(`URL: ${baseUrl}/WhoAmI\n`);
  const data = await apiGet(`${baseUrl}/WhoAmI`, accessToken) as Record<string, unknown>;
  console.log(JSON.stringify(data, null, 2));
}

async function health(baseUrl: string, accessToken: string, token: TokenFile, tokenPath: string): Promise<void> {
  console.log("=== Dynamics 365 Health Check ===");
  console.log(`URL: ${baseUrl.replace("/api/data/v9.2", "")}\n`);

  // Check 1: WhoAmI
  console.log("--- WhoAmI ---");
  try {
    const data = await apiGet(`${baseUrl}/WhoAmI`, accessToken) as Record<string, unknown>;
    console.log("✓ WhoAmI: OK (HTTP 200)");
    console.log(JSON.stringify(data, null, 2));
  } catch (err) {
    console.log(`✗ WhoAmI: FAILED (${err instanceof Error ? err.message : err})`);
  }
  console.log();

  // Check 2: Token info
  console.log("--- Token Info ---");
  console.log(`  File: ${tokenPath}`);
  checkExpiry(token);
  console.log(`  Token type: ${token.tokenType ?? "unknown"}`);
  console.log(`  Tenant: ${token.tenant ?? "unknown"}`);
  console.log(`  Subscription: ${token.subscription ?? "unknown"}`);
  console.log();

  // Check 3: Entity sets
  console.log("--- Entity Sets ---");
  try {
    const data = await apiGet(baseUrl, accessToken) as { value?: Array<{ name: string }> };
    console.log(`✓ Entity Sets: OK (${data.value?.length ?? 0} entity sets available)`);
  } catch (err) {
    console.log(`✗ Entity Sets: FAILED (${err instanceof Error ? err.message : err})`);
  }
}

async function getRecords(baseUrl: string, accessToken: string, resource: string): Promise<void> {
  // Determine full URL
  let fullUrl: string;
  if (resource.startsWith("http")) {
    fullUrl = resource;
  } else if (resource.startsWith("api/")) {
    fullUrl = `${baseUrl.replace("/api/data/v9.2", "")}/${resource}`;
  } else {
    fullUrl = `${baseUrl}/${resource}`;
  }

  console.log(`GET: ${fullUrl}\n`);

  const data = await apiGet(fullUrl, accessToken) as Record<string, unknown>;

  if ("value" in data && Array.isArray(data.value)) {
    console.log(`Records: ${data.value.length}\n`);
    console.log(JSON.stringify(data.value, null, 2));
    if ("@odata.nextLink" in data) {
      console.log(`\nNext page: ${data["@odata.nextLink"]}`);
    }
  } else {
    console.log(JSON.stringify(data, null, 2));
  }
}

async function listEntitySets(baseUrl: string, accessToken: string): Promise<void> {
  console.log("=== Available Entity Sets ===");
  console.log(`URL: ${baseUrl}\n`);

  const data = await apiGet(baseUrl, accessToken) as {
    value?: Array<{ name: string; kind?: string; url: string }>;
  };

  for (const s of data.value ?? []) {
    const kind = s.kind ? ` (${s.kind})` : "";
    console.log(`  ${s.name}${kind} -> ${s.url}`);
  }
}

async function metadata(baseUrl: string, accessToken: string, entity?: string): Promise<void> {
  if (!entity) {
    console.log("=== Entity Metadata (all) ===");
    console.log(`URL: ${baseUrl}/EntityDefinitions\n`);

    const data = await apiGet(`${baseUrl}/EntityDefinitions`, accessToken) as {
      value?: Array<{
        SchemaName: string;
        EntitySetName?: string;
        DisplayName?: { UserLocalizedLabel?: { Label?: string } };
      }>;
    };

    console.log(`Total entities: ${data.value?.length ?? 0}\n`);
    for (const e of data.value ?? []) {
      const display = e.DisplayName?.UserLocalizedLabel?.Label;
      const label = display ? ` (${display})` : "";
      console.log(`  ${e.SchemaName}${label} -> ${e.EntitySetName ?? "unknown"}`);
    }
  } else {
    console.log(`=== Entity Metadata: ${entity} ===`);
    console.log(`URL: ${baseUrl}/EntityDefinitions(LogicalName='${entity}')\n`);

    const data = await apiGet(
      `${baseUrl}/EntityDefinitions(LogicalName='${entity}')`,
      accessToken,
    );
    console.log(JSON.stringify(data, null, 2));
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main(): Promise<void> {
  const args = process.argv.slice(2);

  if (args.length < 2) {
    console.error("Usage: npx tsx dynamics-api.ts <dynamics-url> <action> [resource]");
    console.error("");
    console.error("Actions:");
    console.error("  whoami              Get current user info");
    console.error("  health              Full health check (WhoAmI + token + entity sets)");
    console.error("  get <path>          GET request (e.g. 'accounts' or 'accounts?$top=5')");
    console.error("  list                List all available entity sets");
    console.error("  metadata [entity]   Entity definitions (optionally filter by logical name)");
    process.exit(1);
  }

  const dynamicsUrl = args[0].replace(/\/+$/, "");
  const action = args[1];
  const resource = args[2] ?? "";
  const apiBase = `${dynamicsUrl}/api/data/v9.2`;

  const tokenPath = findTokenFile();
  const token = loadToken(tokenPath);

  if (!token.accessToken) {
    console.error(`ERROR: accessToken is empty in ${tokenPath}`);
    process.exit(1);
  }

  try {
    switch (action) {
      case "whoami":
        await whoami(apiBase, token.accessToken);
        break;
      case "health":
        await health(apiBase, token.accessToken, token, tokenPath);
        break;
      case "get":
        if (!resource) {
          console.error("ERROR: 'get' requires a path argument, e.g.: accounts");
          process.exit(1);
        }
        await getRecords(apiBase, token.accessToken, resource);
        break;
      case "list":
        await listEntitySets(apiBase, token.accessToken);
        break;
      case "metadata":
        await metadata(apiBase, token.accessToken, resource || undefined);
        break;
      default:
        console.error(`ERROR: Unknown action '${action}'`);
        console.error("Available actions: whoami | health | get | list | metadata");
        process.exit(1);
    }
  } catch (err) {
    console.error(`\nERROR: ${err instanceof Error ? err.message : err}`);
    console.error("Check that your token is valid and the Dynamics URL is correct.");
    process.exit(1);
  }
}

main();
