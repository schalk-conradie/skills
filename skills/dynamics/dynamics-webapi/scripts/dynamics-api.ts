#!/usr/bin/env npx tsx
/**
 * Dynamics 365 WebAPI helper — read-only access
 *
 * Usage:
 *   npx tsx dynamics-api.ts <dynamics-url-or-host> whoami
 *   npx tsx dynamics-api.ts <dynamics-url-or-host> health
 *   npx tsx dynamics-api.ts <dynamics-url-or-host> get <path-or-query>
 *   npx tsx dynamics-api.ts <dynamics-url-or-host> list
 *   npx tsx dynamics-api.ts <dynamics-url-or-host> metadata [entity-logical-name]
 */

import { readFileSync, existsSync, rmSync, writeFileSync, renameSync, mkdirSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { homedir } from "node:os";
import { spawnSync } from "node:child_process";

const DATAVERSE_PUBLIC_CLIENT_ID = "51f81489-12ee-4a9e-aaae-a2591f45987d";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TokenFile {
  accessToken: string;
  refreshToken?: string;
  refresh_token?: string;
  expiresIn?: string;
  expiresOn?: string;
  expires_on?: number;
  expiresAt?: number;
  scope?: string;
  subscription?: string;
  tenant?: string;
  tokenType?: string;
}

interface OpenDataverseEnvironment {
  id?: string;
  url?: string;
}

interface OpenDataverseConfig {
  environments?: OpenDataverseEnvironment[];
}

// ---------------------------------------------------------------------------
// Token loading
// ---------------------------------------------------------------------------

function normalizedDynamicsUrlOrUndefined(value: string | undefined): string | undefined {
  if (!value) return undefined;
  const raw = value.trim();
  if (!raw) return undefined;

  const withScheme = /^[a-z][a-z0-9+.-]*:\/\//i.test(raw) ? raw : `https://${raw}`;
  let parsed: URL;
  try {
    parsed = new URL(withScheme);
  } catch {
    return undefined;
  }

  if (!["http:", "https:"].includes(parsed.protocol) || !parsed.host) {
    return undefined;
  }

  return `https://${parsed.host}`;
}

function normalizeDynamicsUrl(value: string): string {
  const normalized = normalizedDynamicsUrlOrUndefined(value);
  if (!normalized) {
    console.error(`ERROR: Invalid Dynamics URL or host: ${value}`);
    process.exit(1);
  }
  return normalized;
}

function localTokenFile(): string {
  return join(process.cwd(), "token.json");
}

function homeDynamicsTokenFile(): string {
  return join(homedir(), ".dynamics", "token.json");
}

function defaultTokenFile(): string {
  return localTokenFile();
}

function loadToken(path: string): TokenFile {
  try {
    return JSON.parse(readFileSync(path, "utf-8"));
  } catch (err) {
    console.error(`ERROR: Failed to parse ${path}: ${err}`);
    process.exit(1);
  }
}

function tryLoadToken(path: string, label: string): TokenFile | undefined {
  try {
    return JSON.parse(readFileSync(path, "utf-8"));
  } catch (err) {
    console.log(`Skipping ${label} token at ${path}; failed to parse JSON: ${err}`);
    return undefined;
  }
}

function writeJsonAtomic(path: string, value: Record<string, unknown>): void {
  const dir = dirname(path);
  if (dir && !existsSync(dir)) mkdirSync(dir, { recursive: true });
  const tmp = join(dir || process.cwd(), `.${basename(path)}.tmp`);
  writeFileSync(tmp, JSON.stringify(value, null, 2), "utf-8");
  renameSync(tmp, path);
}

function tokenExpiryEpoch(token: TokenFile): number {
  if (token.expiresAt) return Number(token.expiresAt);
  if (token.expires_on) return Number(token.expires_on);
  if (token.expiresOn?.trim()) {
    const normalized = token.expiresOn.trim().replace(" ", "T").replace(/\.\d+$/, "");
    const parsed = Date.parse(normalized);
    if (!Number.isNaN(parsed)) return Math.floor(parsed / 1000);
  }
  return 0;
}

function tokenIsExpired(token: TokenFile): boolean {
  const expiresOn = tokenExpiryEpoch(token);
  return !expiresOn || expiresOn <= Math.floor(Date.now() / 1000);
}

function getTenant(token: TokenFile | undefined, explicitTenant?: string): string | undefined {
  return explicitTenant || token?.tenant;
}

function validExistingToken(
  tokenPath: string,
  token: TokenFile | undefined,
  label: string,
): { tokenPath: string; token: TokenFile } | undefined {
  if (!token) return undefined;
  if (!token.accessToken) {
    console.log(`Skipping ${label} token at ${tokenPath}; accessToken is empty.`);
    return undefined;
  }
  if (tokenIsExpired(token)) {
    console.log(`Skipping expired ${label} token at ${tokenPath}.`);
    return undefined;
  }
  return { tokenPath, token };
}

function findOpenDataverseTokenFile(resourceUrl: string): string | undefined {
  const configPath = join(homedir(), ".OpenDataverse", "config.json");
  if (!existsSync(configPath)) return undefined;

  let config: OpenDataverseConfig;
  try {
    config = JSON.parse(readFileSync(configPath, "utf-8"));
  } catch (err) {
    console.log(`Skipping OpenDataverse; failed to parse ${configPath}: ${err}`);
    return undefined;
  }

  if (!Array.isArray(config.environments)) {
    console.log(`Skipping OpenDataverse; ${configPath} has no environments list.`);
    return undefined;
  }

  for (const environment of config.environments) {
    const envUrl = normalizedDynamicsUrlOrUndefined(environment.url);
    if (!envUrl || envUrl.toLowerCase() !== resourceUrl.toLowerCase() || !environment.id) {
      continue;
    }

    const tokenPath = join(homedir(), ".OpenDataverse", "tokens", `token-${environment.id}.json`);
    if (existsSync(tokenPath)) return tokenPath;
    console.log(`OpenDataverse matched ${resourceUrl}, but token file is missing: ${tokenPath}`);
    return undefined;
  }

  return undefined;
}

async function refreshOpenDataverseToken(
  resourceUrl: string,
  tokenPath: string,
  token: TokenFile,
  explicitTenant?: string,
): Promise<TokenFile | undefined> {
  const refreshToken = token.refreshToken ?? token.refresh_token;
  if (!refreshToken) {
    console.log(`OpenDataverse token at ${tokenPath} is expired and has no refreshToken.`);
    return undefined;
  }

  const tenant = explicitTenant ?? "organizations";
  const body = new URLSearchParams({
    client_id: DATAVERSE_PUBLIC_CLIENT_ID,
    grant_type: "refresh_token",
    refresh_token: refreshToken,
    scope: `${resourceUrl}/user_impersonation offline_access`,
  });

  let response: Response;
  try {
    response = await fetch(
      `https://login.microsoftonline.com/${encodeURIComponent(tenant)}/oauth2/v2.0/token`,
      {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body,
      },
    );
  } catch (err) {
    console.log(`OpenDataverse token refresh failed: ${err}`);
    return undefined;
  }

  if (!response.ok) {
    const text = await response.text().catch(() => "");
    console.log(`OpenDataverse token refresh failed: HTTP ${response.status} ${response.statusText}: ${text.slice(0, 300)}`);
    return undefined;
  }

  const result = await response.json() as {
    access_token?: string;
    refresh_token?: string;
    expires_in?: number | string;
    token_type?: string;
    scope?: string;
  };
  if (!result.access_token) {
    console.log("OpenDataverse token refresh failed: token endpoint returned no access_token.");
    return undefined;
  }

  const expiresIn = Number(result.expires_in ?? 0);
  const refreshed: TokenFile = {
    ...token,
    accessToken: result.access_token,
    refreshToken: result.refresh_token ?? refreshToken,
  };
  if (Number.isFinite(expiresIn) && expiresIn > 0) {
    refreshed.expiresAt = Math.floor(Date.now() / 1000) + expiresIn;
  }
  if (result.token_type) refreshed.tokenType = result.token_type;
  if (result.scope) refreshed.scope = result.scope;

  writeJsonAtomic(tokenPath, refreshed as unknown as Record<string, unknown>);
  console.log(`Refreshed OpenDataverse token: ${tokenPath}`);
  return refreshed;
}

async function getOpenDataverseToken(
  resourceUrl: string,
  explicitTenant?: string,
): Promise<{ tokenPath: string; token: TokenFile } | undefined> {
  const tokenPath = findOpenDataverseTokenFile(resourceUrl);
  if (!tokenPath) return undefined;

  const token = tryLoadToken(tokenPath, "OpenDataverse");
  if (!token) return undefined;
  if (!token.accessToken) {
    console.log(`Skipping OpenDataverse token at ${tokenPath}; accessToken is empty.`);
    return undefined;
  }
  if (!tokenIsExpired(token)) {
    return { tokenPath, token };
  }

  console.log(`OpenDataverse token expired at ${tokenPath}; refreshing with stored refreshToken.`);
  const refreshed = await refreshOpenDataverseToken(resourceUrl, tokenPath, token, explicitTenant);
  if (refreshed?.accessToken && !tokenIsExpired(refreshed)) {
    return { tokenPath, token: refreshed };
  }
  return undefined;
}

function generateToken(resourceUrl: string, tokenPath: string, tenant?: string): TokenFile {
  const azProbe = spawnSync("az", ["--version"], { stdio: "ignore", shell: process.platform === "win32" });
  if (azProbe.error || azProbe.status !== 0) {
    console.error("ERROR: Azure CLI 'az' was not found on PATH.");
    console.error("Install Azure CLI or add it to PATH, then reopen the shell.");
    process.exit(1);
  }

  console.log("Logging into Azure CLI...");
  console.log("-------------------------------------------------------");
  const loginArgs = ["login", "--allow-no-subscriptions"];
  if (tenant) loginArgs.push("--tenant", tenant);

  const login = spawnSync("az", loginArgs, { stdio: "inherit", shell: process.platform === "win32" });
  if (login.status !== 0) {
    console.error("ERROR: Azure login failed.");
    process.exit(1);
  }

  console.log();
  console.log(`Attempting to get access token for resource: ${resourceUrl}`);
  console.log("-------------------------------------------------------");
  const tokenArgs = ["account", "get-access-token", "--resource", resourceUrl, "--output", "json"];
  if (tenant) tokenArgs.push("--tenant", tenant);

  const tokenResult = spawnSync("az", tokenArgs, {
    encoding: "utf-8",
    shell: process.platform === "win32",
  });

  if (tokenResult.status !== 0) {
    rmSync(tokenPath, { force: true });
    if (tokenResult.stderr) console.error(tokenResult.stderr.trim());
    console.error("ERROR: Failed to generate token.");
    process.exit(1);
  }

  let token: TokenFile;
  try {
    token = JSON.parse(tokenResult.stdout);
  } catch (err) {
    rmSync(tokenPath, { force: true });
    console.error(`ERROR: Azure CLI returned invalid token JSON: ${err}`);
    process.exit(1);
  }

  writeJsonAtomic(tokenPath, token as unknown as Record<string, unknown>);
  console.log(`Token saved to: ${tokenPath}`);
  return token;
}

async function ensureToken(resourceUrl: string, explicitTenant?: string): Promise<{ tokenPath: string; token: TokenFile }> {
  const tokenPath = localTokenFile();
  if (existsSync(tokenPath)) {
    const token = tryLoadToken(tokenPath, "local");
    const validToken = validExistingToken(tokenPath, token, "local");
    if (validToken) return validToken;
  }

  const openDataverseToken = await getOpenDataverseToken(resourceUrl, explicitTenant);
  if (openDataverseToken) return openDataverseToken;

  const homeTokenPath = homeDynamicsTokenFile();
  if (existsSync(homeTokenPath)) {
    const homeToken = tryLoadToken(homeTokenPath, "home ~/.dynamics");
    const validHomeToken = validExistingToken(homeTokenPath, homeToken, "home ~/.dynamics");
    if (validHomeToken) return validHomeToken;
    console.log(`Using Azure CLI as last resort for ${homeTokenPath}.`);
    return {
      tokenPath: homeTokenPath,
      token: generateToken(resourceUrl, homeTokenPath, getTenant(homeToken, explicitTenant)),
    };
  }

  const defaultPath = defaultTokenFile();
  console.log("No valid token found in ./token.json, OpenDataverse, or ~/.dynamics/token.json.");
  return { tokenPath: defaultPath, token: generateToken(resourceUrl, defaultPath, explicitTenant) };
}

function checkExpiry(token: TokenFile): void {
  const expiresOn = tokenExpiryEpoch(token);
  if (!expiresOn) {
    console.log("  Expiry: Not set");
    return;
  }
  const now = Math.floor(Date.now() / 1000);
  const remaining = expiresOn - now;
  if (remaining > 0) {
    const date = new Date(expiresOn * 1000).toISOString().replace("T", " ").slice(0, 19);
    console.log(`  Expiry: Valid (${remaining}s remaining, expires ${date})`);
  } else {
    const date = new Date(expiresOn * 1000).toISOString().replace("T", " ").slice(0, 19);
    console.log(`  Expired: ${Math.abs(remaining)}s ago (${date})`);
  }
}

// ---------------------------------------------------------------------------
// HTTP helper
// ---------------------------------------------------------------------------

async function apiGet(url: string, accessToken: string): Promise<unknown> {
  url = encodeUrlForRequest(url);
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

function encodeUrlForRequest(url: string): string {
  const parsed = new URL(url);
  parsed.pathname = parsed.pathname
    .split("/")
    .map((part) => encodeURIComponent(decodeURIComponent(part)))
    .join("/");
  parsed.search = parsed.search.replace(/ /g, "%20");
  return parsed.toString();
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

  const requestUrl = encodeUrlForRequest(fullUrl);
  console.log(`GET: ${requestUrl}\n`);

  const data = await apiGet(requestUrl, accessToken) as Record<string, unknown>;

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
  let explicitTenant: string | undefined;
  const tenantIndex = args.indexOf("--tenant");
  if (tenantIndex !== -1) {
    if (!args[tenantIndex + 1]) {
      console.error("ERROR: --tenant requires a tenant id or domain");
      process.exit(1);
    }
    explicitTenant = args[tenantIndex + 1];
    args.splice(tenantIndex, 2);
  }

  if (args.length < 2) {
    console.error("Usage: npx tsx dynamics-api.ts [--tenant <tenant>] <dynamics-url-or-host> <action> [resource]");
    console.error("");
    console.error("Actions:");
    console.error("  whoami              Get current user info");
    console.error("  health              Full health check (WhoAmI + token + entity sets)");
    console.error("  get <path>          GET request (e.g. 'accounts' or 'accounts?$top=5')");
    console.error("  list                List all available entity sets");
    console.error("  metadata [entity]   Entity definitions (optionally filter by logical name)");
    process.exit(1);
  }

  const dynamicsUrl = normalizeDynamicsUrl(args[0]);
  const action = args[1];
  const resource = args[2] ?? "";
  const apiBase = `${dynamicsUrl}/api/data/v9.2`;

  const { tokenPath, token } = await ensureToken(dynamicsUrl, explicitTenant);

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
