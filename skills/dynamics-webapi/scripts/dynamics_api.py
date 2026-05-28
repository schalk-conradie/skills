#!/usr/bin/env python3
"""Dynamics 365 WebAPI helper - read-only access.

Usage:
  python scripts/dynamics_api.py <dynamics-url> whoami
  python scripts/dynamics_api.py <dynamics-url> health
  python scripts/dynamics_api.py <dynamics-url> get <path-or-query>
  python scripts/dynamics_api.py <dynamics-url> list
  python scripts/dynamics_api.py <dynamics-url> metadata [entity-logical-name]
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def find_token_file() -> Path:
    cwd = Path.cwd() / "token.json"
    home = Path.home() / ".dynamics" / "token.json"
    if cwd.exists():
        return cwd
    if home.exists():
        return home

    print("ERROR: token.json not found in current directory or ~/.dynamics/", file=sys.stderr)
    print("Expected format:", file=sys.stderr)
    print(
        json.dumps(
            {
                "accessToken": "...",
                "expiresIn": "",
                "expires_on": 0,
                "subscription": "",
                "tenant": "",
                "tokenType": "Bearer",
            },
            indent=4,
        ),
        file=sys.stderr,
    )
    raise SystemExit(1)


def load_token(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"ERROR: Failed to parse {path}: {exc}", file=sys.stderr)
        raise SystemExit(1)


def check_expiry(token: dict[str, Any]) -> None:
    expires_on = int(token.get("expires_on") or 0)
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
    if len(args) < 2:
        print("Usage: python scripts/dynamics_api.py <dynamics-url> <action> [resource]", file=sys.stderr)
        print("", file=sys.stderr)
        print("Actions:", file=sys.stderr)
        print("  whoami              Get current user info", file=sys.stderr)
        print("  health              Full health check (WhoAmI + token + entity sets)", file=sys.stderr)
        print("  get <path>          GET request (e.g. 'accounts' or 'accounts?$top=5')", file=sys.stderr)
        print("  list                List all available entity sets", file=sys.stderr)
        print("  metadata [entity]   Entity definitions (optionally filter by logical name)", file=sys.stderr)
        raise SystemExit(1)

    dynamics_url = args[0].rstrip("/")
    action = args[1]
    resource = args[2] if len(args) > 2 else ""
    api_base = f"{dynamics_url}/api/data/v9.2"

    token_path = find_token_file()
    token = load_token(token_path)
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
