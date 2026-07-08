#!/usr/bin/env python3
"""Create a Glaze app source tree from Glaze's installed official template."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import plistlib
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


GLAZE_RESOURCES_DIR = Path("/Applications/Glaze.app/Contents/Resources")
TEMPLATE_DIR = GLAZE_RESOURCES_DIR / "template-app"
TEMPLATE_LAUNCHER_DIR = GLAZE_RESOURCES_DIR / "template-app-shell.app"
DEFAULT_GLAZE_APPS_DIR = Path.home() / "Library/Application Support/app.glaze.macos.main/apps"

ENTITLEMENTS = {
    "com.apple.security.automation.apple-events": True,
    "com.apple.security.cs.disable-library-validation": True,
    "com.apple.security.device.audio-input": True,
    "com.apple.security.device.camera": True,
    "com.apple.security.personal-information.addressbook": True,
    "com.apple.security.personal-information.calendars": True,
    "com.apple.security.personal-information.location": True,
    "com.apple.security.scripting-targets": {
        "com.apple.shortcuts.events": ["com.apple.shortcuts.run"],
    },
}


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "glaze-app"


def app_id_from_name(name: str) -> str:
    app_id = re.sub(r"[^a-z0-9]", "", name.lower())
    return (app_id or "glazeapp")[:32]


def safe_file_name(value: str) -> str:
    return re.sub(r"[/:\0]", "-", value).strip() or "Glaze App"


def run(cmd: list[str], cwd: Path) -> None:
    print(f"[create-glaze-app] {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def update_json(path: Path, updater) -> None:
    data = json.loads(path.read_text())
    updater(data)
    path.write_text(json.dumps(data, indent=2) + "\n")


def copy_template(output: Path, force: bool) -> None:
    if not TEMPLATE_DIR.is_dir():
        raise SystemExit(f"Template not found: {TEMPLATE_DIR}")

    if output.exists():
        if not force:
            raise SystemExit(f"Output already exists: {output}. Pass --force to replace it.")
        shutil.rmtree(output)

    shutil.copytree(
        TEMPLATE_DIR,
        output,
        ignore=shutil.ignore_patterns("node_modules", "build", ".build", ".git"),
    )


def rewrite_metadata(output: Path, name: str, product_name: str, description: str, icon_description: str | None) -> tuple[str, str]:
    package_name = slugify(name)
    glaze_id = app_id_from_name(package_name)
    created_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

    def update_package(data: dict) -> None:
        data["id"] = glaze_id
        data["name"] = package_name
        data["productName"] = product_name
        data["description"] = description
        data["iconDescription"] = icon_description or f"A Glaze desktop app named {product_name}."
        glaze = data.setdefault("glaze", {})
        glaze["createdAt"] = created_at
        glaze.pop("updatedAt", None)

    update_json(output / "package.json", update_package)

    lock_path = output / "package-lock.json"
    if lock_path.exists():
        def update_lock(data: dict) -> None:
            data["name"] = package_name
            packages = data.get("packages")
            if isinstance(packages, dict) and "" in packages:
                packages[""]["name"] = package_name

        update_json(lock_path, update_lock)

    return package_name, glaze_id


def read_package(source_dir: Path) -> dict:
    return json.loads((source_dir / "package.json").read_text())


def copy_icon(source_dir: Path, destination: Path, icon: Path | None, launcher_template: Path) -> None:
    candidates = [
        icon,
        source_dir / "app-icon.icns",
        launcher_template / "Contents" / "Resources" / "app-icon.icns",
        launcher_template / "Contents" / "Resources" / "template-appicon.icns",
    ]
    icon_source = next((path for path in candidates if path and path.exists()), None)
    if not icon_source:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(icon_source, destination)


def ensure_source_package_files(source_dir: Path, product_name: str, description: str) -> None:
    memory_dir = source_dir / ".glaze_memory"
    memory_dir.mkdir(exist_ok=True)
    context_path = memory_dir / "PROJECT-CONTEXT.md"
    history_path = memory_dir / "PROJECT-HISTORY.md"

    if not context_path.exists():
        context_path.write_text(
            f"# Project Context\n\n## Overview\n\n- **App Name:** {product_name}\n"
            f"- **Purpose:** {description}\n",
        )

    if not history_path.exists():
        history_path.write_text(
            f"# Project History\n\n### Generated\n\n- Created from Glaze's installed official template.\n",
        )


def ensure_git_repo(source_dir: Path) -> None:
    if (source_dir / ".git").exists():
        return
    if not shutil.which("git"):
        raise SystemExit("git not found; cannot create the source repository required by a .glaze project package.")

    run(["git", "-c", "init.defaultBranch=main", "init"], source_dir)
    run(["git", "add", "."], source_dir)
    run(
        [
            "git",
            "-c",
            "user.name=Glaze App Generator",
            "-c",
            "user.email=glaze-generator.local",
            "commit",
            "-m",
            "Initial generated Glaze app",
        ],
        source_dir,
    )


def write_runtime_payload(source_dir: Path, runtime_dir: Path, icon: Path | None, launcher_template: Path) -> None:
    build_dir = source_dir / "build"
    if not build_dir.is_dir():
        raise SystemExit(f"Build output not found: {build_dir}. Run npm run build before creating an app bundle.")

    if runtime_dir.exists() or runtime_dir.is_symlink():
        if runtime_dir.is_symlink() or runtime_dir.is_file():
            runtime_dir.unlink()
        else:
            shutil.rmtree(runtime_dir)

    runtime_dir.mkdir(parents=True)
    shutil.copytree(build_dir, runtime_dir / "build")

    package = read_package(source_dir)
    runtime_package = {
        key: package[key]
        for key in ["id", "name", "version", "productName", "description", "type", "glaze"]
        if key in package
    }
    (runtime_dir / "package.json").write_text(json.dumps(runtime_package, indent=2) + "\n")
    copy_icon(source_dir, runtime_dir / "app-icon.icns", icon, launcher_template)


def update_info_plist(app_path: Path, product_name: str, glaze_id: str, executable_name: str) -> None:
    info_path = app_path / "Contents" / "Info.plist"
    with info_path.open("rb") as handle:
        info = plistlib.load(handle)

    bundle_id = f"app.glaze.macos.{glaze_id}-local"
    info["CFBundleDisplayName"] = product_name
    info["CFBundleExecutable"] = executable_name
    info["CFBundleIconFile"] = "app-icon"
    info["CFBundleIconName"] = "app-icon"
    info["CFBundleIdentifier"] = bundle_id
    info["CFBundleName"] = product_name
    info["CFBundleShortVersionString"] = "1.0.0"
    info["CFBundleURLTypes"][0]["CFBundleURLName"] = bundle_id
    info["CFBundleURLTypes"][0]["CFBundleURLSchemes"] = [f"glaze-{glaze_id}-local", "com.glaze"]

    with info_path.open("wb") as handle:
        plistlib.dump(info, handle, fmt=plistlib.FMT_XML)


def sign_app(app_path: Path) -> None:
    if not shutil.which("codesign"):
        raise SystemExit("codesign not found; cannot sign the generated .app bundle.")

    with tempfile.TemporaryDirectory() as temp_dir:
        entitlements_path = Path(temp_dir) / "entitlements.plist"
        with entitlements_path.open("wb") as handle:
            plistlib.dump(ENTITLEMENTS, handle, fmt=plistlib.FMT_XML)

        run(
            [
                "codesign",
                "--force",
                "--deep",
                "--options",
                "runtime",
                "--entitlements",
                str(entitlements_path),
                "--sign",
                "-",
                str(app_path),
            ],
            app_path.parent,
        )

    run(["codesign", "--verify", "--deep", "--strict", str(app_path)], app_path.parent)


def create_app_bundle(
    source_dir: Path,
    app_output: Path,
    product_name: str,
    glaze_id: str,
    icon: Path | None,
    launcher_template: Path,
    force: bool,
    skip_sign: bool,
) -> None:
    if not launcher_template.is_dir():
        raise SystemExit(f"Launcher template not found: {launcher_template}")

    app_output = app_output.expanduser().resolve()
    if app_output.exists():
        if not force:
            raise SystemExit(f"App output already exists: {app_output}. Pass --force to replace it.")
        shutil.rmtree(app_output)

    shutil.copytree(launcher_template, app_output, symlinks=True, ignore=shutil.ignore_patterns("_CodeSignature"))

    contents_dir = app_output / "Contents"
    macos_dir = contents_dir / "MacOS"
    resources_dir = contents_dir / "Resources"

    with (contents_dir / "Info.plist").open("rb") as handle:
        template_info = plistlib.load(handle)

    old_executable = macos_dir / template_info["CFBundleExecutable"]
    executable_name = safe_file_name(product_name)
    new_executable = macos_dir / executable_name
    if old_executable != new_executable:
        old_executable.rename(new_executable)
    new_executable.chmod(0o755)

    write_runtime_payload(source_dir, resources_dir / "glaze-runtime", icon, launcher_template)
    copy_icon(source_dir, resources_dir / "app-icon.icns", icon, launcher_template)
    update_info_plist(app_output, product_name, glaze_id, executable_name)

    if not skip_sign:
        sign_app(app_output)

    print(f"[create-glaze-app] Created app bundle: {app_output}")


def install_into_glaze(
    source_dir: Path,
    apps_dir: Path,
    package_name: str,
    product_name: str,
    glaze_id: str,
    description: str,
    icon: Path | None,
    launcher_template: Path,
    force: bool,
    skip_sign: bool,
) -> Path:
    apps_dir = apps_dir.expanduser().resolve()
    install_dir = apps_dir / f"{package_name}-local-{glaze_id}"

    if install_dir.exists():
        if not force:
            raise SystemExit(f"Glaze app already exists: {install_dir}. Pass --force to replace it.")
        shutil.rmtree(install_dir)

    install_dir.mkdir(parents=True)
    try:
        write_runtime_payload(source_dir, install_dir / ".glaze", icon, launcher_template)

        sources_dir = install_dir / ".glaze-sources"
        shutil.copytree(
            source_dir,
            sources_dir,
            ignore=shutil.ignore_patterns("build", ".build"),
        )
        ensure_source_package_files(sources_dir, product_name, description)
        ensure_git_repo(sources_dir)

        create_app_bundle(
            source_dir=source_dir,
            app_output=install_dir / f"{safe_file_name(product_name)}.app",
            product_name=product_name,
            glaze_id=glaze_id,
            icon=icon,
            launcher_template=launcher_template,
            force=force,
            skip_sign=skip_sign,
        )
    except Exception:
        shutil.rmtree(install_dir, ignore_errors=True)
        raise

    print(f"[create-glaze-app] Installed Glaze app: {install_dir}")
    return install_dir


def create_project_package(
    source_dir: Path,
    project_output: Path,
    package_name: str,
    product_name: str,
    glaze_id: str,
    description: str,
    icon: Path | None,
    launcher_template: Path,
    force: bool,
) -> None:
    project_output = project_output.expanduser().resolve()
    if project_output.suffix != ".glaze":
        project_output = project_output.with_suffix(".glaze")

    if project_output.exists():
        if not force:
            raise SystemExit(f"Glaze project output already exists: {project_output}. Pass --force to replace it.")
        shutil.rmtree(project_output)

    package = read_package(source_dir)
    exported_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    app_version = package.get("version", "1.0.0")
    app_id = f"{package_name}-local-{glaze_id}"

    project_dir = project_output / "project"
    runtime_dir = project_dir / ".glaze"
    sources_dir = project_dir / ".glaze-sources"
    chat_dir = project_output / "chat"
    logs_dir = project_output / "data" / "logs"

    project_dir.mkdir(parents=True)
    chat_dir.mkdir(parents=True)
    logs_dir.mkdir(parents=True)

    shutil.copytree(
        source_dir,
        sources_dir,
        ignore=shutil.ignore_patterns("node_modules", "build", ".build"),
    )
    ensure_source_package_files(sources_dir, product_name, description)
    ensure_git_repo(sources_dir)
    write_runtime_payload(source_dir, runtime_dir, icon, launcher_template)

    manifest = {
        "format": "app.glaze.project-package",
        "version": 1,
        "exportedAt": exported_at,
        "app": {
            "appId": app_id,
            "projectId": glaze_id,
            "name": package_name,
            "displayName": product_name,
            "description": description,
            "version": app_version,
        },
        "contents": {
            "sources": "project/.glaze-sources",
            "runtime": "project/.glaze",
            "chat": "chat/sessions.json",
            "logs": "data/logs",
        },
    }
    (project_output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

    sessions = {
        "format": "app.glaze.agent-chat",
        "version": 1,
        "exportedAt": exported_at,
        "projectPath": str(runtime_dir),
        "sessions": [],
        "requests": [],
        "messages": [],
    }
    (chat_dir / "sessions.json").write_text(json.dumps(sessions, indent=2) + "\n")

    print(f"[create-glaze-app] Created Glaze project package: {project_output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="Directory to create.")
    parser.add_argument("--name", required=True, help="Package-style app name. Slugified automatically.")
    parser.add_argument("--product-name", help="Human app name. Defaults to title-cased --name.")
    parser.add_argument("--description", default="Custom Glaze desktop app.")
    parser.add_argument("--icon-description")
    parser.add_argument("--icon", type=Path, help="Optional .icns file to use for the app and runtime payload.")
    parser.add_argument("--app-output", type=Path, help="Optional .app bundle path to create after building.")
    parser.add_argument("--project-output", type=Path, help="Optional importable .glaze project package path.")
    parser.add_argument("--launcher-template", type=Path, default=TEMPLATE_LAUNCHER_DIR, help="Glaze launcher .app template.")
    parser.add_argument(
        "--glaze-apps-dir",
        type=Path,
        default=DEFAULT_GLAZE_APPS_DIR,
        help="Glaze apps directory to install into.",
    )
    parser.add_argument(
        "--no-install-to-glaze",
        action="store_true",
        help="Only create the source tree and requested exports; do not install into Glaze's apps directory.",
    )
    parser.add_argument("--force", action="store_true", help="Replace output if it already exists.")
    parser.add_argument("--skip-install", action="store_true", help="Do not run npm ci.")
    parser.add_argument("--skip-checks", action="store_true", help="Do not run type-check and lint.")
    parser.add_argument("--skip-build", action="store_true", help="Do not run npm run build.")
    parser.add_argument("--skip-sign", action="store_true", help="Create the .app bundle without codesigning it.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output = args.output.expanduser().resolve()
    product_name = args.product_name or slugify(args.name).replace("-", " ").title()
    icon = args.icon.expanduser().resolve() if args.icon else None
    launcher_template = args.launcher_template.expanduser().resolve()

    copy_template(output, args.force)
    package_name, glaze_id = rewrite_metadata(output, args.name, product_name, args.description, args.icon_description)

    if not args.skip_install:
        run(["npm", "ci", "--ignore-scripts"], output)

    if not args.skip_checks:
        run(["npm", "run", "type-check"], output)
        run(["npm", "run", "lint"], output)

    if not args.skip_build:
        run(["npm", "run", "build"], output)

    if not args.no_install_to_glaze:
        install_into_glaze(
            source_dir=output,
            apps_dir=args.glaze_apps_dir,
            package_name=package_name,
            product_name=product_name,
            glaze_id=glaze_id,
            description=args.description,
            icon=icon,
            launcher_template=launcher_template,
            force=args.force,
            skip_sign=args.skip_sign,
        )

    if args.app_output:
        create_app_bundle(
            source_dir=output,
            app_output=args.app_output,
            product_name=product_name,
            glaze_id=glaze_id,
            icon=icon,
            launcher_template=launcher_template,
            force=args.force,
            skip_sign=args.skip_sign,
        )

    if args.project_output:
        create_project_package(
            source_dir=output,
            project_output=args.project_output,
            package_name=package_name,
            product_name=product_name,
            glaze_id=glaze_id,
            description=args.description,
            icon=icon,
            launcher_template=launcher_template,
            force=args.force,
        )

    print(f"[create-glaze-app] Created {product_name}: {output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode)
