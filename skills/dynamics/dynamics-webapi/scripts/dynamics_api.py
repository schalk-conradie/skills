#!/usr/bin/env python3
"""Dynamics 365 WebAPI helper - read-only access.

Usage:
  python scripts/dynamics_api.py <dynamics-url-or-host> whoami
  python scripts/dynamics_api.py <dynamics-url-or-host> health
  python scripts/dynamics_api.py <dynamics-url-or-host> get <path-or-query>
  python scripts/dynamics_api.py <dynamics-url-or-host> list
  python scripts/dynamics_api.py <dynamics-url-or-host> metadata [entity-logical-name]
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


DATAVERSE_PUBLIC_CLIENT_ID = "51f81489-12ee-4a9e-aaae-a2591f45987d"


def normalized_dynamics_url_or_none(value: str) -> str | None:
    raw = value.strip()
    if not raw:
        return None

    if "://" not in raw:
        raw = f"https://{raw}"

    try:
        parsed = urllib.parse.urlsplit(raw)
    except ValueError:
        return None

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    return f"https://{parsed.netloc.rstrip('/')}"


def normalize_dynamics_url(value: str) -> str:
    normalized = normalized_dynamics_url_or_none(value)
    if not normalized:
        print(f"ERROR: Invalid Dynamics URL or host: {value}", file=sys.stderr)
        raise SystemExit(1)
    return normalized


def local_token_file() -> Path:
    return Path.cwd() / "token.json"


def home_dynamics_token_file() -> Path:
    return Path.home() / ".dynamics" / "token.json"


def default_token_file() -> Path:
    return local_token_file()


def load_token(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: Failed to parse {path}: {exc}", file=sys.stderr)
        raise SystemExit(1)


def try_load_token(path: Path, label: str) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Skipping {label} token at {path}; failed to parse JSON: {exc}")
        return None


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(value, indent=2), encoding="utf-8")
    tmp.replace(path)


def token_expiry_epoch(token: dict[str, Any]) -> int:
    expires_at = token.get("expiresAt")
    if expires_at:
        try:
            return int(expires_at)
        except (TypeError, ValueError):
            return 0

    expires_on = token.get("expires_on")
    if expires_on:
        try:
            return int(expires_on)
        except (TypeError, ValueError):
            return 0

    expires_on_text = token.get("expiresOn")
    if isinstance(expires_on_text, str) and expires_on_text.strip():
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                return int(datetime.strptime(expires_on_text, fmt).timestamp())
            except ValueError:
                continue

    return 0


def token_is_expired(token: dict[str, Any]) -> bool:
    expires_on = token_expiry_epoch(token)
    return not expires_on or expires_on <= int(time.time())


def get_tenant(token: dict[str, Any] | None, explicit_tenant: str | None) -> str | None:
    if explicit_tenant:
        return explicit_tenant
    if token and token.get("tenant"):
        return str(token["tenant"])
    return None


def valid_existing_token(
    token_path: Path,
    token: dict[str, Any] | None,
    label: str,
) -> tuple[Path, dict[str, Any]] | None:
    if not token:
        return None
    if not token.get("accessToken"):
        print(f"Skipping {label} token at {token_path}; accessToken is empty.")
        return None
    if token_is_expired(token):
        print(f"Skipping expired {label} token at {token_path}.")
        return None
    return token_path, token


def find_open_dataverse_token_file(resource_url: str) -> Path | None:
    config_path = Path.home() / ".OpenDataverse" / "config.json"
    if not config_path.exists():
        return None

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Skipping OpenDataverse; failed to parse {config_path}: {exc}")
        return None

    environments = config.get("environments")
    if not isinstance(environments, list):
        print(f"Skipping OpenDataverse; {config_path} has no environments list.")
        return None

    for environment in environments:
        if not isinstance(environment, dict):
            continue
        env_url = environment.get("url")
        env_id = environment.get("id")
        if not isinstance(env_url, str) or not isinstance(env_id, str):
            continue
        normalized_env_url = normalized_dynamics_url_or_none(env_url)
        if normalized_env_url and normalized_env_url.lower() == resource_url.lower():
            token_path = config_path.parent / "tokens" / f"token-{env_id}.json"
            if token_path.exists():
                return token_path
            print(f"OpenDataverse matched {resource_url}, but token file is missing: {token_path}")
            return None

    return None


def refresh_open_dataverse_token(
    resource_url: str,
    token_path: Path,
    token: dict[str, Any],
    explicit_tenant: str | None,
) -> dict[str, Any] | None:
    refresh_token = token.get("refreshToken") or token.get("refresh_token")
    if not isinstance(refresh_token, str) or not refresh_token:
        print(f"OpenDataverse token at {token_path} is expired and has no refreshToken.")
        return None

    tenant = explicit_tenant or "organizations"
    token_url = f"https://login.microsoftonline.com/{urllib.parse.quote(tenant, safe='')}/oauth2/v2.0/token"
    form = urllib.parse.urlencode(
        {
            "client_id": DATAVERSE_PUBLIC_CLIENT_ID,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": f"{resource_url}/user_impersonation offline_access",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        token_url,
        data=form,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"OpenDataverse token refresh failed: HTTP {exc.code} {exc.reason}: {body[:300]}")
        return None
    except Exception as exc:
        print(f"OpenDataverse token refresh failed: {exc}")
        return None

    access_token = result.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        print("OpenDataverse token refresh failed: token endpoint returned no access_token.")
        return None

    try:
        expires_in = int(result.get("expires_in", 0))
    except (TypeError, ValueError):
        expires_in = 0

    refreshed = dict(token)
    refreshed["accessToken"] = access_token
    refreshed["refreshToken"] = result.get("refresh_token") or refresh_token
    if expires_in:
        refreshed["expiresAt"] = int(time.time()) + expires_in
    if result.get("token_type"):
        refreshed["tokenType"] = result["token_type"]
    if result.get("scope"):
        refreshed["scope"] = result["scope"]

    write_json_atomic(token_path, refreshed)
    print(f"Refreshed OpenDataverse token: {token_path}")
    return refreshed


def get_open_dataverse_token(
    resource_url: str,
    explicit_tenant: str | None,
) -> tuple[Path, dict[str, Any]] | None:
    token_path = find_open_dataverse_token_file(resource_url)
    if not token_path:
        return None

    token = try_load_token(token_path, "OpenDataverse")
    if not token:
        return None
    if not token.get("accessToken"):
        print(f"Skipping OpenDataverse token at {token_path}; accessToken is empty.")
        return None
    if not token_is_expired(token):
        return token_path, token

    print(f"OpenDataverse token expired at {token_path}; refreshing with stored refreshToken.")
    refreshed = refresh_open_dataverse_token(resource_url, token_path, token, explicit_tenant)
    if refreshed and refreshed.get("accessToken") and not token_is_expired(refreshed):
        return token_path, refreshed
    return None


def run_az(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess:
    az_path = shutil.which("az")
    if not az_path:
        print("ERROR: Azure CLI 'az' was not found on PATH.", file=sys.stderr)
        print("Install Azure CLI or add it to PATH, then reopen the shell.", file=sys.stderr)
        raise SystemExit(1)

    command = [az_path, *args]
    return subprocess.run(command, **kwargs)


def generate_token(resource_url: str, token_path: Path, tenant: str | None = None) -> dict[str, Any]:
    print("Logging into Azure CLI...")
    print("-------------------------------------------------------")
    login_cmd = ["login", "--allow-no-subscriptions"]
    if tenant:
        login_cmd.extend(["--tenant", tenant])

    login = run_az(login_cmd)
    if login.returncode != 0:
        print("ERROR: Azure login failed.", file=sys.stderr)
        raise SystemExit(1)

    print()
    print(f"Attempting to get access token for resource: {resource_url}")
    print("-------------------------------------------------------")
    token_cmd = ["account", "get-access-token", "--resource", resource_url, "--output", "json"]
    if tenant:
        token_cmd.extend(["--tenant", tenant])

    token_result = run_az(token_cmd, capture_output=True, text=True)
    if token_result.returncode != 0:
        token_path.unlink(missing_ok=True)
        if token_result.stderr:
            print(token_result.stderr.strip(), file=sys.stderr)
        print("ERROR: Failed to generate token.", file=sys.stderr)
        raise SystemExit(1)

    try:
        token = json.loads(token_result.stdout)
    except Exception as exc:
        token_path.unlink(missing_ok=True)
        print(f"ERROR: Azure CLI returned invalid token JSON: {exc}", file=sys.stderr)
        raise SystemExit(1)

    token_path.write_text(json.dumps(token, indent=2), encoding="utf-8")
    print(f"Token saved to: {token_path}")
    return token


def ensure_token(resource_url: str, explicit_tenant: str | None = None) -> tuple[Path, dict[str, Any]]:
    token_path = local_token_file()
    if token_path.exists():
        token = try_load_token(token_path, "local")
        valid_token = valid_existing_token(token_path, token, "local")
        if valid_token:
            return valid_token

    open_dataverse_token = get_open_dataverse_token(resource_url, explicit_tenant)
    if open_dataverse_token:
        return open_dataverse_token

    home_token_path = home_dynamics_token_file()
    if home_token_path.exists():
        home_token = try_load_token(home_token_path, "home ~/.dynamics")
        valid_home_token = valid_existing_token(home_token_path, home_token, "home ~/.dynamics")
        if valid_home_token:
            return valid_home_token
        print(f"Using Azure CLI as last resort for {home_token_path}.")
        return home_token_path, generate_token(
            resource_url,
            home_token_path,
            get_tenant(home_token, explicit_tenant),
        )

    token_path = default_token_file()
    print("No valid token found in ./token.json, OpenDataverse, or ~/.dynamics/token.json.")
    return token_path, generate_token(resource_url, token_path, explicit_tenant)


def check_expiry(token: dict[str, Any]) -> None:
    expires_on = token_expiry_epoch(token)
    if not expires_on:
        print("  Expiry: Not set")
        return

    remaining = expires_on - int(time.time())
    expires_at = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(expires_on))
    if remaining > 0:
        print(f"  Expiry: Valid ({remaining}s remaining, expires {expires_at})")
    else:
        print(f"  Expired: {abs(remaining)}s ago ({expires_at})")


def api_get(url: str, access_token: str) -> Any:
    request = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {access_token}",
            "OData-MaxVersion": "4.0",
            "OData-Version": "4.0",
            "Accept": "application/json",
            "Content-Type": "application/json; charset=utf-8",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        message = f"HTTP {exc.code} {exc.reason}"
        if body:
            message += f": {body[:500]}"
        raise RuntimeError(message) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc

    return json.loads(body) if body else {}


def whoami(base_url: str, access_token: str) -> None:
    print("=== Dynamics 365 WhoAmI ===")
    print(f"URL: {base_url}/WhoAmI\n")
    print(json.dumps(api_get(f"{base_url}/WhoAmI", access_token), indent=2))


def health(base_url: str, access_token: str, token: dict[str, Any], token_path: Path) -> None:
    print("=== Dynamics 365 Health Check ===")
    print(f"URL: {base_url.replace('/api/data/v9.2', '')}\n")

    print("--- WhoAmI ---")
    try:
        data = api_get(f"{base_url}/WhoAmI", access_token)
        print("OK WhoAmI: OK (HTTP 200)")
        print(json.dumps(data, indent=2))
    except Exception as exc:
        print(f"FAILED WhoAmI: FAILED ({exc})")
    print()

    print("--- Token Info ---")
    print(f"  File: {token_path}")
    check_expiry(token)
    print(f"  Token type: {token.get('tokenType', 'unknown')}")
    print(f"  Tenant: {token.get('tenant', 'unknown')}")
    print(f"  Subscription: {token.get('subscription', 'unknown')}")
    print()

    print("--- Entity Sets ---")
    try:
        data = api_get(base_url, access_token)
        print(f"OK Entity Sets: OK ({len(data.get('value', []))} entity sets available)")
    except Exception as exc:
        print(f"FAILED Entity Sets: FAILED ({exc})")


def get_records(base_url: str, access_token: str, resource: str) -> None:
    if resource.startswith("http"):
        full_url = resource
    elif resource.startswith("api/"):
        full_url = f"{base_url.replace('/api/data/v9.2', '')}/{resource}"
    else:
        full_url = f"{base_url}/{resource}"

    print(f"GET: {full_url}\n")
    data = api_get(full_url, access_token)

    if isinstance(data, dict) and isinstance(data.get("value"), list):
        print(f"Records: {len(data['value'])}\n")
        print(json.dumps(data["value"], indent=2))
        next_link = data.get("@odata.nextLink")
        if next_link:
            print(f"\nNext page: {next_link}")
    else:
        print(json.dumps(data, indent=2))


def list_entity_sets(base_url: str, access_token: str) -> None:
    print("=== Available Entity Sets ===")
    print(f"URL: {base_url}\n")
    data = api_get(base_url, access_token)

    for item in data.get("value", []):
        kind = f" ({item['kind']})" if item.get("kind") else ""
        print(f"  {item.get('name')}{kind} -> {item.get('url')}")


def metadata(base_url: str, access_token: str, entity: str | None = None) -> None:
    if not entity:
        print("=== Entity Metadata (all) ===")
        print(f"URL: {base_url}/EntityDefinitions\n")
        data = api_get(f"{base_url}/EntityDefinitions", access_token)
        values = data.get("value", [])

        print(f"Total entities: {len(values)}\n")
        for item in values:
            display = (
                item.get("DisplayName", {})
                .get("UserLocalizedLabel", {})
                .get("Label")
            )
            label = f" ({display})" if display else ""
            print(f"  {item.get('SchemaName')}{label} -> {item.get('EntitySetName', 'unknown')}")
        return

    print(f"=== Entity Metadata: {entity} ===")
    print(f"URL: {base_url}/EntityDefinitions(LogicalName='{entity}')\n")
    print(json.dumps(api_get(f"{base_url}/EntityDefinitions(LogicalName='{entity}')", access_token), indent=2))


def main() -> None:
    args = sys.argv[1:]
    explicit_tenant = None
    if "--tenant" in args:
        index = args.index("--tenant")
        if index + 1 >= len(args):
            print("ERROR: --tenant requires a tenant id or domain", file=sys.stderr)
            raise SystemExit(1)
        explicit_tenant = args[index + 1]
        del args[index : index + 2]

    if len(args) < 2:
        print("Usage: python scripts/dynamics_api.py [--tenant <tenant>] <dynamics-url-or-host> <action> [resource]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Actions:", file=sys.stderr)
        print("  whoami              Get current user info", file=sys.stderr)
        print("  health              Full health check (WhoAmI + token + entity sets)", file=sys.stderr)
        print("  get <path>          GET request (e.g. 'accounts' or 'accounts?$top=5')", file=sys.stderr)
        print("  list                List all available entity sets", file=sys.stderr)
        print("  metadata [entity]   Entity definitions (optionally filter by logical name)", file=sys.stderr)
        raise SystemExit(1)

    dynamics_url = normalize_dynamics_url(args[0])
    action = args[1]
    resource = args[2] if len(args) > 2 else ""
    api_base = f"{dynamics_url}/api/data/v9.2"

    token_path, token = ensure_token(dynamics_url, explicit_tenant)
    access_token = token.get("accessToken")
    if not access_token:
        print(f"ERROR: accessToken is empty in {token_path}", file=sys.stderr)
        raise SystemExit(1)

    try:
        if action == "whoami":
            whoami(api_base, access_token)
        elif action == "health":
            health(api_base, access_token, token, token_path)
        elif action == "get":
            if not resource:
                print("ERROR: 'get' requires a path argument, e.g.: accounts", file=sys.stderr)
                raise SystemExit(1)
            get_records(api_base, access_token, resource)
        elif action == "list":
            list_entity_sets(api_base, access_token)
        elif action == "metadata":
            metadata(api_base, access_token, resource or None)
        else:
            print(f"ERROR: Unknown action '{action}'", file=sys.stderr)
            print("Available actions: whoami | health | get | list | metadata", file=sys.stderr)
            raise SystemExit(1)
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        print("Check that your token is valid and the Dynamics URL is correct.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
