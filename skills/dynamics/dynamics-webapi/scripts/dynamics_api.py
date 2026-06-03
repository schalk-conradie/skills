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


def normalize_dynamics_url(value: str) -> str:
    raw = value.strip()
    if not raw:
        print("ERROR: Dynamics URL is empty.", file=sys.stderr)
        raise SystemExit(1)

    if "://" not in raw:
        raw = f"https://{raw}"

    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        print(f"ERROR: Invalid Dynamics URL or host: {value}", file=sys.stderr)
        raise SystemExit(1)

    return f"https://{parsed.netloc.rstrip('/')}"


def find_token_file() -> Path | None:
    cwd = Path.cwd() / "token.json"
    home = Path.home() / ".dynamics" / "token.json"
    if cwd.exists():
        return cwd
    if home.exists():
        return home
    return None


def default_token_file() -> Path:
    return Path.cwd() / "token.json"


def load_token(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: Failed to parse {path}: {exc}", file=sys.stderr)
        raise SystemExit(1)


def token_expiry_epoch(token: dict[str, Any]) -> int:
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
    token_path = find_token_file()
    token = load_token(token_path) if token_path else None

    if token_path is None:
        token_path = default_token_file()
        print("token.json not found in current directory or ~/.dynamics/.")
        return token_path, generate_token(resource_url, token_path, explicit_tenant)

    if not token.get("accessToken"):
        print(f"accessToken is empty in {token_path}; generating a new token.")
        return token_path, generate_token(resource_url, token_path, get_tenant(token, explicit_tenant))

    if token_is_expired(token):
        print(f"Token expired in {token_path}; generating a new token.")
        return token_path, generate_token(resource_url, token_path, get_tenant(token, explicit_tenant))

    return token_path, token


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
