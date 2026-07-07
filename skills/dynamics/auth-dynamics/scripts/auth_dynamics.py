#!/usr/bin/env python3
"""Get a Dynamics 365 / Dataverse WebAPI bearer token."""

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


def try_load_token(path: Path, label: str) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Skipping {label} token at {path}; failed to parse JSON: {exc}", file=sys.stderr)
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


def valid_existing_token(
    token_path: Path,
    token: dict[str, Any] | None,
    label: str,
) -> tuple[Path, dict[str, Any]] | None:
    if not token:
        return None
    if not token.get("accessToken"):
        print(f"Skipping {label} token at {token_path}; accessToken is empty.", file=sys.stderr)
        return None
    if token_is_expired(token):
        print(f"Skipping expired {label} token at {token_path}.", file=sys.stderr)
        return None
    return token_path, token


def find_open_dataverse_token_file(resource_url: str) -> Path | None:
    config_path = Path.home() / ".OpenDataverse" / "config.json"
    if not config_path.exists():
        return None

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"Skipping OpenDataverse; failed to parse {config_path}: {exc}", file=sys.stderr)
        return None

    environments = config.get("environments")
    if not isinstance(environments, list):
        print(f"Skipping OpenDataverse; {config_path} has no environments list.", file=sys.stderr)
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
            print(f"OpenDataverse matched {resource_url}, but token file is missing: {token_path}", file=sys.stderr)
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
        print(f"OpenDataverse token at {token_path} is expired and has no refreshToken.", file=sys.stderr)
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
        print(f"OpenDataverse token refresh failed: HTTP {exc.code} {exc.reason}: {body[:300]}", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"OpenDataverse token refresh failed: {exc}", file=sys.stderr)
        return None

    access_token = result.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        print("OpenDataverse token refresh failed: token endpoint returned no access_token.", file=sys.stderr)
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
    print(f"Refreshed OpenDataverse token: {token_path}", file=sys.stderr)
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
        print(f"Skipping OpenDataverse token at {token_path}; accessToken is empty.", file=sys.stderr)
        return None
    if not token_is_expired(token):
        return token_path, token

    print(f"OpenDataverse token expired at {token_path}; refreshing with stored refreshToken.", file=sys.stderr)
    refreshed = refresh_open_dataverse_token(resource_url, token_path, token, explicit_tenant)
    if refreshed and refreshed.get("accessToken") and not token_is_expired(refreshed):
        return token_path, refreshed
    return None


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
        raise SystemExit(1)
    return subprocess.run([az_path, *args], **kwargs)


def generate_token(resource_url: str, token_path: Path, tenant: str | None = None) -> dict[str, Any]:
    login_cmd = ["login", "--allow-no-subscriptions"]
    if tenant:
        login_cmd.extend(["--tenant", tenant])

    print("Logging into Azure CLI...", file=sys.stderr)
    login = run_az(login_cmd)
    if login.returncode != 0:
        print("ERROR: Azure login failed.", file=sys.stderr)
        raise SystemExit(1)

    token_cmd = ["account", "get-access-token", "--resource", resource_url, "--output", "json"]
    if tenant:
        token_cmd.extend(["--tenant", tenant])

    print(f"Getting access token for resource: {resource_url}", file=sys.stderr)
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

    write_json_atomic(token_path, token)
    print(f"Token saved to: {token_path}", file=sys.stderr)
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
        print(f"Using Azure CLI as last resort for {home_token_path}.", file=sys.stderr)
        return home_token_path, generate_token(resource_url, home_token_path, get_tenant(home_token, explicit_tenant))

    print("No valid token found in ./token.json, OpenDataverse, or ~/.dynamics/token.json.", file=sys.stderr)
    return token_path, generate_token(resource_url, token_path, explicit_tenant)


def expiry_summary(token: dict[str, Any]) -> str:
    expires_on = token_expiry_epoch(token)
    if not expires_on:
        return "not set"

    remaining = expires_on - int(time.time())
    expires_at = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(expires_on))
    if remaining > 0:
        return f"valid for {remaining}s, expires {expires_at}"
    return f"expired {abs(remaining)}s ago, expired {expires_at}"


def parse_args(argv: list[str]) -> tuple[str | None, str, str, bool]:
    args = list(argv)
    explicit_tenant = None
    output_format = "summary"
    print_token = False

    if "--tenant" in args:
        index = args.index("--tenant")
        if index + 1 >= len(args):
            print("ERROR: --tenant requires a tenant id or domain", file=sys.stderr)
            raise SystemExit(1)
        explicit_tenant = args[index + 1]
        del args[index : index + 2]

    if "--format" in args:
        index = args.index("--format")
        if index + 1 >= len(args):
            print("ERROR: --format requires summary, token, json, or header", file=sys.stderr)
            raise SystemExit(1)
        output_format = args[index + 1]
        del args[index : index + 2]

    if "--print-token" in args:
        print_token = True
        args.remove("--print-token")

    if output_format not in {"summary", "token", "json", "header"}:
        print("ERROR: --format must be summary, token, json, or header", file=sys.stderr)
        raise SystemExit(1)

    if len(args) != 1:
        print("Usage: python scripts/auth_dynamics.py [--tenant <tenant>] <dynamics-url-or-host> [--print-token] [--format summary|token|json|header]", file=sys.stderr)
        raise SystemExit(1)

    return explicit_tenant, args[0], output_format, print_token


def main() -> None:
    explicit_tenant, url_arg, output_format, print_token = parse_args(sys.argv[1:])
    dynamics_url = normalize_dynamics_url(url_arg)
    token_path, token = ensure_token(dynamics_url, explicit_tenant)
    access_token = token.get("accessToken")
    if not isinstance(access_token, str) or not access_token:
        print(f"ERROR: accessToken is empty in {token_path}", file=sys.stderr)
        raise SystemExit(1)

    if print_token:
        output_format = "token"

    if output_format == "token":
        print(access_token)
    elif output_format == "header":
        print(f"Authorization: Bearer {access_token}")
    elif output_format == "json":
        print(
            json.dumps(
                {
                    "dynamicsUrl": dynamics_url,
                    "tokenPath": str(token_path),
                    "expiresOn": token_expiry_epoch(token),
                    "tokenType": token.get("tokenType", "Bearer"),
                    "accessToken": access_token,
                },
                indent=2,
            )
        )
    else:
        print(f"Dynamics URL: {dynamics_url}")
        print(f"Token file: {token_path}")
        print(f"Token type: {token.get('tokenType', 'Bearer')}")
        print(f"Expiry: {expiry_summary(token)}")
        print("Access token: hidden (use --print-token or --format header when required)")


if __name__ == "__main__":
    main()
