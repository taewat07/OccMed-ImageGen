#!/usr/bin/env python3
"""Create, render, index, and validate portable image-design catalogs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SCHEMA_VERSION = "1.0"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
IMAGE_EXTENSIONS = {
    ".avif", ".bmp", ".gif", ".heic", ".heif", ".jpeg", ".jpg",
    ".png", ".tif", ".tiff", ".webp",
}
ISO_IMAGE_BRANDS = {
    b"avif", b"avis", b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1",
}
OBSERVATION_GROUPS = (
    "composition", "visual_hierarchy", "geometry", "color", "typography",
    "linework", "texture", "lighting", "medium", "motifs", "mood",
)
LIST_GROUPS = {
    "transferable_design_system": (
        "invariants", "flexible_traits", "design_rules", "avoid",
    ),
    "content_specific_elements": (
        "subjects", "text", "logos_or_marks", "incidental_details",
        "do_not_transfer",
    ),
}


class CatalogError(Exception):
    """Raised for a user-correctable catalog error."""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def read_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise CatalogError(f"missing required file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CatalogError(
            f"malformed JSON in {path}: line {exc.lineno}, column {exc.colno}: {exc.msg}"
        ) from exc
    except OSError as exc:
        raise CatalogError(f"cannot read {path}: {exc}") from exc


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_source_name(name: str) -> str:
    path = Path(name)
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip("-.") or "reference"
    suffix = path.suffix.lower()
    return f"{stem}{suffix}"


def require_slug(slug: str) -> None:
    if not SLUG_RE.fullmatch(slug):
        raise CatalogError(
            f"invalid slug {slug!r}; use lowercase letters, digits, and single hyphens"
        )


def require_image(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise CatalogError(f"source is not a readable file: {path}")
    if resolved.suffix.lower() not in IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(IMAGE_EXTENSIONS))
        raise CatalogError(f"unsupported image extension for {path}; allowed: {allowed}")
    if resolved.stat().st_size <= 0:
        raise CatalogError(f"source image is empty: {path}")
    if not has_supported_image_signature(resolved):
        raise CatalogError(f"source does not contain a recognized image signature: {path}")
    return resolved


def has_supported_image_signature(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            header = handle.read(32)
    except OSError:
        return False
    if header.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if header.startswith(b"\xff\xd8\xff"):
        return True
    if header.startswith((b"GIF87a", b"GIF89a", b"BM", b"II*\x00", b"MM\x00*")):
        return True
    if len(header) >= 12 and header.startswith(b"RIFF") and header[8:12] == b"WEBP":
        return True
    if len(header) >= 12 and header[4:8] == b"ftyp" and header[8:12] in ISO_IMAGE_BRANDS:
        return True
    return False


def title_from_slug(slug: str) -> str:
    return " ".join(word.capitalize() for word in slug.split("-"))


def empty_observations() -> dict[str, list[Any]]:
    return {name: [] for name in OBSERVATION_GROUPS}


def build_draft(slug: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
    now = utc_now()
    return {
        "schema_version": SCHEMA_VERSION,
        "identity": {
            "slug": slug,
            "title": title_from_slug(slug),
            "summary": "",
            "status": "draft",
        },
        "provenance": {
            "created_at": now,
            "updated_at": now,
            "attribution_notes": "",
        },
        "taxonomy": {"tags": [], "collections": []},
        "sources": sources,
        "observations": empty_observations(),
        "transferable_design_system": {
            "invariants": [],
            "flexible_traits": [],
            "design_rules": [],
            "avoid": [],
        },
        "content_specific_elements": {
            "subjects": [],
            "text": [],
            "logos_or_marks": [],
            "incidental_details": [],
            "do_not_transfer": [],
        },
        "prompt_packet": {
            "direction": "",
            "positive_prompt": "",
            "negative_prompt": "",
            "variables": {"subject": "Describe the new subject here"},
            "essential_invariants": [],
            "flexible_characteristics": [],
        },
    }


def expect_object(value: Any, location: str, errors: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        errors.append(f"{location} must be an object")
        return {}
    return value


def expect_string(value: Any, location: str, errors: list[str], *, allow_empty: bool = True) -> str:
    if not isinstance(value, str):
        errors.append(f"{location} must be a string")
        return ""
    if not allow_empty and not value.strip():
        errors.append(f"{location} must not be empty")
    return value


def expect_string_list(value: Any, location: str, errors: list[str], *, unique: bool = False) -> list[str]:
    if not isinstance(value, list):
        errors.append(f"{location} must be an array")
        return []
    result: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{location}[{index}] must be a non-empty string")
        else:
            result.append(item)
    if unique and len(result) != len(set(result)):
        errors.append(f"{location} must not contain duplicates")
    return result


def expect_exact_keys(obj: dict[str, Any], required: Iterable[str], location: str, errors: list[str]) -> None:
    expected = set(required)
    missing = expected - set(obj)
    extra = set(obj) - expected
    for key in sorted(missing):
        errors.append(f"{location}.{key} is required")
    for key in sorted(extra):
        errors.append(f"{location}.{key} is not allowed")


def valid_datetime(value: str) -> bool:
    if not value:
        return False
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        datetime.fromisoformat(candidate)
    except ValueError:
        return False
    return True


def validate_design(data: Any, entry_dir: Path, *, verify_sources: bool = True) -> list[str]:
    errors: list[str] = []
    root = expect_object(data, "$", errors)
    root_keys = (
        "schema_version", "identity", "provenance", "taxonomy", "sources",
        "observations", "transferable_design_system", "content_specific_elements",
        "prompt_packet",
    )
    expect_exact_keys(root, root_keys, "$", errors)

    if root.get("schema_version") != SCHEMA_VERSION:
        errors.append(
            f"$.schema_version must be {SCHEMA_VERSION!r}, got {root.get('schema_version')!r}"
        )

    identity = expect_object(root.get("identity"), "$.identity", errors)
    expect_exact_keys(identity, ("slug", "title", "summary", "status"), "$.identity", errors)
    slug = expect_string(identity.get("slug"), "$.identity.slug", errors, allow_empty=False)
    if slug and not SLUG_RE.fullmatch(slug):
        errors.append("$.identity.slug must use lowercase letters, digits, and single hyphens")
    if slug and entry_dir.name != slug:
        errors.append(f"$.identity.slug {slug!r} does not match entry directory {entry_dir.name!r}")
    expect_string(identity.get("title"), "$.identity.title", errors, allow_empty=False)
    expect_string(identity.get("summary"), "$.identity.summary", errors)
    status = identity.get("status")
    if status not in {"draft", "complete"}:
        errors.append("$.identity.status must be 'draft' or 'complete'")

    provenance = expect_object(root.get("provenance"), "$.provenance", errors)
    expect_exact_keys(
        provenance, ("created_at", "updated_at", "attribution_notes"),
        "$.provenance", errors,
    )
    for field in ("created_at", "updated_at"):
        value = expect_string(provenance.get(field), f"$.provenance.{field}", errors, allow_empty=False)
        if value and not valid_datetime(value):
            errors.append(f"$.provenance.{field} must be an ISO 8601 date-time")
    expect_string(provenance.get("attribution_notes"), "$.provenance.attribution_notes", errors)

    taxonomy = expect_object(root.get("taxonomy"), "$.taxonomy", errors)
    expect_exact_keys(taxonomy, ("tags", "collections"), "$.taxonomy", errors)
    expect_string_list(taxonomy.get("tags"), "$.taxonomy.tags", errors, unique=True)
    expect_string_list(taxonomy.get("collections"), "$.taxonomy.collections", errors, unique=True)

    sources = root.get("sources")
    if not isinstance(sources, list) or not sources:
        errors.append("$.sources must be a non-empty array")
        sources = []
    seen_paths: set[str] = set()
    for index, raw_source in enumerate(sources):
        location = f"$.sources[{index}]"
        source = expect_object(raw_source, location, errors)
        expect_exact_keys(source, ("path", "original_name", "sha256", "bytes", "role"), location, errors)
        relative = expect_string(source.get("path"), f"{location}.path", errors, allow_empty=False)
        expect_string(source.get("original_name"), f"{location}.original_name", errors, allow_empty=False)
        digest = expect_string(source.get("sha256"), f"{location}.sha256", errors, allow_empty=False)
        if digest and not SHA256_RE.fullmatch(digest):
            errors.append(f"{location}.sha256 must be 64 lowercase hexadecimal characters")
        size = source.get("bytes")
        if not isinstance(size, int) or isinstance(size, bool) or size < 1:
            errors.append(f"{location}.bytes must be a positive integer")
        expect_string(source.get("role"), f"{location}.role", errors, allow_empty=False)

        if relative:
            pure = PurePosixPath(relative)
            if pure.is_absolute() or ".." in pure.parts or len(pure.parts) != 2 or pure.parts[0] != "sources":
                errors.append(f"{location}.path must be a safe path directly under sources/")
            elif relative in seen_paths:
                errors.append(f"{location}.path duplicates {relative!r}")
            else:
                seen_paths.add(relative)
                source_path = entry_dir.joinpath(*pure.parts)
                if verify_sources:
                    if not source_path.is_file():
                        errors.append(f"{location}.path is missing: {relative}")
                    else:
                        if source_path.suffix.lower() not in IMAGE_EXTENSIONS or not has_supported_image_signature(source_path):
                            errors.append(f"{location}.path is not a recognized supported image: {relative}")
                        actual_size = source_path.stat().st_size
                        if isinstance(size, int) and actual_size != size:
                            errors.append(f"{location}.bytes does not match {relative}")
                        if SHA256_RE.fullmatch(digest or "") and sha256_file(source_path) != digest:
                            errors.append(f"{location}.sha256 does not match {relative}")

    observations = expect_object(root.get("observations"), "$.observations", errors)
    expect_exact_keys(observations, OBSERVATION_GROUPS, "$.observations", errors)
    observation_count = 0
    for group in OBSERVATION_GROUPS:
        items = observations.get(group)
        location = f"$.observations.{group}"
        if not isinstance(items, list):
            errors.append(f"{location} must be an array")
            continue
        observation_count += len(items)
        for index, raw_item in enumerate(items):
            item_location = f"{location}[{index}]"
            item = expect_object(raw_item, item_location, errors)
            expect_exact_keys(item, ("statement", "evidence", "confidence", "inferred"), item_location, errors)
            expect_string(item.get("statement"), f"{item_location}.statement", errors, allow_empty=False)
            expect_string_list(item.get("evidence"), f"{item_location}.evidence", errors)
            if item.get("confidence") not in {"high", "medium", "low"}:
                errors.append(f"{item_location}.confidence must be high, medium, or low")
            if not isinstance(item.get("inferred"), bool):
                errors.append(f"{item_location}.inferred must be a boolean")

    for section_name, fields in LIST_GROUPS.items():
        section = expect_object(root.get(section_name), f"$.{section_name}", errors)
        expect_exact_keys(section, fields, f"$.{section_name}", errors)
        for field in fields:
            expect_string_list(section.get(field), f"$.{section_name}.{field}", errors)

    packet = expect_object(root.get("prompt_packet"), "$.prompt_packet", errors)
    packet_fields = (
        "direction", "positive_prompt", "negative_prompt", "variables",
        "essential_invariants", "flexible_characteristics",
    )
    expect_exact_keys(packet, packet_fields, "$.prompt_packet", errors)
    for field in ("direction", "positive_prompt", "negative_prompt"):
        expect_string(packet.get(field), f"$.prompt_packet.{field}", errors)
    variables = expect_object(packet.get("variables"), "$.prompt_packet.variables", errors)
    if "subject" not in variables:
        errors.append("$.prompt_packet.variables.subject is required")
    for key, value in variables.items():
        if not isinstance(key, str) or not key:
            errors.append("$.prompt_packet.variables keys must be non-empty strings")
        expect_string(value, f"$.prompt_packet.variables.{key}", errors)
    expect_string_list(packet.get("essential_invariants"), "$.prompt_packet.essential_invariants", errors)
    expect_string_list(packet.get("flexible_characteristics"), "$.prompt_packet.flexible_characteristics", errors)

    if status == "complete":
        required_text = {
            "$.identity.summary": identity.get("summary"),
            "$.prompt_packet.direction": packet.get("direction"),
            "$.prompt_packet.positive_prompt": packet.get("positive_prompt"),
            "$.prompt_packet.negative_prompt": packet.get("negative_prompt"),
        }
        for location, value in required_text.items():
            if not isinstance(value, str) or not value.strip():
                errors.append(f"{location} must not be empty when status is complete")
        if observation_count == 0:
            errors.append("$.observations must contain at least one observation when status is complete")
        system = root.get("transferable_design_system")
        if isinstance(system, dict) and not system.get("invariants"):
            errors.append("$.transferable_design_system.invariants must not be empty when status is complete")
        if isinstance(system, dict) and not system.get("design_rules"):
            errors.append("$.transferable_design_system.design_rules must not be empty when status is complete")
        if not packet.get("essential_invariants"):
            errors.append("$.prompt_packet.essential_invariants must not be empty when status is complete")

    return errors


def markdown_list(values: Any) -> str:
    if not isinstance(values, list) or not values:
        return "_None recorded._\n"
    return "".join(f"- {value}\n" for value in values)


def render_design(data: dict[str, Any]) -> str:
    identity = data["identity"]
    taxonomy = data["taxonomy"]
    lines = [
        f"# {identity['title']}",
        "",
        "<!-- Generated from design.json by design_catalog.py. Do not edit manually. -->",
        "",
        identity["summary"] or "_Draft entry; analysis is not complete._",
        "",
        "## Identity",
        "",
        f"- **Slug:** `{identity['slug']}`",
        f"- **Status:** `{identity['status']}`",
        f"- **Tags:** {', '.join(f'`{value}`' for value in taxonomy['tags']) or '_None_'}",
        f"- **Collections:** {', '.join(f'`{value}`' for value in taxonomy['collections']) or '_None_'}",
        "",
        "## Sources",
        "",
        "| File | Role | SHA-256 |",
        "| --- | --- | --- |",
    ]
    for source in data["sources"]:
        lines.append(f"| [{source['original_name']}]({source['path']}) | {source['role']} | `{source['sha256']}` |")

    lines.extend(["", "## Visual Observations", ""])
    for group in OBSERVATION_GROUPS:
        lines.extend([f"### {group.replace('_', ' ').title()}", ""])
        items = data["observations"][group]
        if not items:
            lines.extend(["_None recorded._", ""])
            continue
        for item in items:
            kind = "inference" if item["inferred"] else "observed"
            evidence = "; ".join(item["evidence"]) or "No evidence recorded"
            lines.append(f"- **{item['statement']}** — {kind}, {item['confidence']} confidence. Evidence: {evidence}")
        lines.append("")

    lines.extend(["## Transferable Design System", ""])
    for field in LIST_GROUPS["transferable_design_system"]:
        lines.extend([f"### {field.replace('_', ' ').title()}", "", markdown_list(data["transferable_design_system"][field]).rstrip(), ""])

    lines.extend(["## Content-Specific Elements", ""])
    for field in LIST_GROUPS["content_specific_elements"]:
        lines.extend([f"### {field.replace('_', ' ').title()}", "", markdown_list(data["content_specific_elements"][field]).rstrip(), ""])

    lines.extend([
        "## Provider-Neutral Prompt Packet",
        "",
        "```json",
        json.dumps(data["prompt_packet"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Provenance",
        "",
        f"- **Created:** `{data['provenance']['created_at']}`",
        f"- **Updated:** `{data['provenance']['updated_at']}`",
        f"- **Attribution notes:** {data['provenance']['attribution_notes'] or '_None_'}",
        "",
    ])
    return "\n".join(lines)


def entry_dirs(catalog_dir: Path) -> list[Path]:
    entries_dir = catalog_dir / "entries"
    if not entries_dir.is_dir():
        raise CatalogError(f"missing entries directory: {entries_dir}")
    return sorted(
        (path for path in entries_dir.iterdir() if path.is_dir()),
        key=lambda path: path.name,
    )


def catalog_payload(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "entries": entries}


def build_catalog_outputs(catalog_dir: Path) -> tuple[str, str, list[str]]:
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_slugs: set[str] = set()
    for directory in entry_dirs(catalog_dir):
        try:
            data = read_json(directory / "design.json")
        except CatalogError as exc:
            errors.append(str(exc))
            continue
        entry_errors = validate_design(data, directory)
        errors.extend(f"{directory.name}: {error}" for error in entry_errors)
        if not isinstance(data, dict) or not isinstance(data.get("identity"), dict):
            continue
        identity = data["identity"]
        slug = identity.get("slug")
        if not isinstance(slug, str):
            continue
        if slug in seen_slugs:
            errors.append(f"duplicate identity slug: {slug}")
            continue
        seen_slugs.add(slug)
        taxonomy = data.get("taxonomy") if isinstance(data.get("taxonomy"), dict) else {}
        records.append({
            "slug": slug,
            "title": identity.get("title", ""),
            "summary": identity.get("summary", ""),
            "status": identity.get("status", "draft"),
            "tags": taxonomy.get("tags", []),
            "collections": taxonomy.get("collections", []),
            "source_count": len(data.get("sources", [])) if isinstance(data.get("sources"), list) else 0,
            "design_json": f"entries/{directory.name}/design.json",
            "design_markdown": f"entries/{directory.name}/DESIGN.md",
        })
    records.sort(key=lambda item: item["slug"])
    catalog_json = json_text(catalog_payload(records))

    lines = [
        "# Design Catalog",
        "",
        "<!-- Generated by design_catalog.py. Do not edit manually. -->",
        "",
    ]
    if not records:
        lines.extend(["_No design entries yet._", ""])
    else:
        lines.extend([
            "| Design | Status | Tags | Collections | Sources |",
            "| --- | --- | --- | --- | ---: |",
        ])
        for record in records:
            tags = ", ".join(record["tags"]) or "—"
            collections = ", ".join(record["collections"]) or "—"
            lines.append(
                f"| [{record['title']}]({record['design_markdown']}) | "
                f"{record['status']} | {tags} | {collections} | {record['source_count']} |"
            )
        lines.append("")
    return catalog_json, "\n".join(lines), errors


def require_catalog(catalog_dir: Path) -> Path:
    resolved = catalog_dir.expanduser().resolve()
    if not resolved.is_dir():
        raise CatalogError(f"catalog directory does not exist: {catalog_dir}")
    if not (resolved / "entries").is_dir():
        raise CatalogError(f"not a design catalog; missing {resolved / 'entries'}")
    return resolved


def cmd_init(args: argparse.Namespace) -> None:
    catalog_dir = Path(args.catalog_dir).expanduser().resolve()
    if catalog_dir.exists() and not catalog_dir.is_dir():
        raise CatalogError(f"catalog path is not a directory: {catalog_dir}")
    if catalog_dir.exists() and any(catalog_dir.iterdir()):
        raise CatalogError(f"refusing to initialize non-empty directory: {catalog_dir}")
    catalog_dir.mkdir(parents=True, exist_ok=True)
    (catalog_dir / "entries").mkdir()
    write_text(catalog_dir / "catalog.json", json_text(catalog_payload([])))
    write_text(
        catalog_dir / "CATALOG.md",
        "# Design Catalog\n\n<!-- Generated by design_catalog.py. Do not edit manually. -->\n\n_No design entries yet._\n",
    )
    print(f"initialized catalog: {catalog_dir}")


def cmd_new(args: argparse.Namespace) -> None:
    catalog_dir = require_catalog(Path(args.catalog_dir))
    require_slug(args.slug)
    if not args.source:
        raise CatalogError("at least one --source image is required")
    entry_dir = catalog_dir / "entries" / args.slug
    if entry_dir.exists():
        raise CatalogError(f"entry slug already exists: {args.slug}")

    source_paths = [require_image(Path(value)) for value in args.source]
    entry_dir.mkdir()
    sources_dir = entry_dir / "sources"
    sources_dir.mkdir()
    records: list[dict[str, Any]] = []
    try:
        for index, source in enumerate(source_paths, start=1):
            destination_name = f"{index:02d}-{safe_source_name(source.name)}"
            destination = sources_dir / destination_name
            shutil.copy2(source, destination)
            records.append({
                "path": f"sources/{destination_name}",
                "original_name": source.name,
                "sha256": sha256_file(destination),
                "bytes": destination.stat().st_size,
                "role": "primary reference" if index == 1 else "supporting reference",
            })
        draft = build_draft(args.slug, records)
        write_text(entry_dir / "design.json", json_text(draft))
        write_text(entry_dir / "DESIGN.md", render_design(draft))
        catalog_json, catalog_markdown, errors = build_catalog_outputs(catalog_dir)
        if errors:
            raise CatalogError("cannot reindex after creating entry:\n" + "\n".join(errors))
        write_text(catalog_dir / "catalog.json", catalog_json)
        write_text(catalog_dir / "CATALOG.md", catalog_markdown)
    except Exception:
        shutil.rmtree(entry_dir)
        raise
    print(f"created entry: {entry_dir}")


def cmd_render(args: argparse.Namespace) -> None:
    entry_dir = Path(args.entry_dir).expanduser().resolve()
    if not entry_dir.is_dir():
        raise CatalogError(f"entry directory does not exist: {entry_dir}")
    data = read_json(entry_dir / "design.json")
    errors = validate_design(data, entry_dir)
    if errors:
        raise CatalogError("entry validation failed:\n" + "\n".join(errors))
    write_text(entry_dir / "DESIGN.md", render_design(data))
    print(f"rendered entry: {entry_dir / 'DESIGN.md'}")


def cmd_reindex(args: argparse.Namespace) -> None:
    catalog_dir = require_catalog(Path(args.catalog_dir))
    catalog_json, catalog_markdown, errors = build_catalog_outputs(catalog_dir)
    if errors:
        raise CatalogError("catalog validation failed:\n" + "\n".join(errors))
    write_text(catalog_dir / "catalog.json", catalog_json)
    write_text(catalog_dir / "CATALOG.md", catalog_markdown)
    print(f"reindexed catalog: {catalog_dir}")


def validate_entry_path(entry_dir: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = read_json(entry_dir / "design.json")
    except CatalogError as exc:
        return [str(exc)]
    errors.extend(validate_design(data, entry_dir))
    if not errors and isinstance(data, dict):
        expected = render_design(data)
        markdown_path = entry_dir / "DESIGN.md"
        try:
            actual = markdown_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            errors.append(f"missing generated file: {markdown_path}")
        except OSError as exc:
            errors.append(f"cannot read {markdown_path}: {exc}")
        else:
            if actual != expected:
                errors.append(f"stale generated file: {markdown_path}")
    return errors


def cmd_validate(args: argparse.Namespace) -> None:
    target = Path(args.target).expanduser().resolve()
    if not target.is_dir():
        raise CatalogError(f"validation target is not a directory: {target}")

    if (target / "entries").is_dir():
        catalog_json, catalog_markdown, errors = build_catalog_outputs(target)
        for entry_dir in entry_dirs(target):
            errors.extend(f"{entry_dir.name}: {error}" for error in validate_entry_path(entry_dir))
        expected_files = {
            target / "catalog.json": catalog_json,
            target / "CATALOG.md": catalog_markdown,
        }
        for path, expected in expected_files.items():
            try:
                actual = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                errors.append(f"missing generated file: {path}")
            except OSError as exc:
                errors.append(f"cannot read {path}: {exc}")
            else:
                if actual != expected:
                    errors.append(f"stale generated file: {path}")
    elif target.name and (target / "design.json").exists():
        errors = validate_entry_path(target)
    else:
        raise CatalogError(f"target is neither a design catalog nor an entry: {target}")

    errors = list(dict.fromkeys(errors))
    if errors:
        raise CatalogError("validation failed:\n" + "\n".join(errors))
    print(f"valid: {target}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create, render, reindex, and validate image-design catalogs."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="initialize an empty catalog")
    init_parser.add_argument("catalog_dir")
    init_parser.set_defaults(func=cmd_init)

    new_parser = subparsers.add_parser("new", help="create a draft entry and copy source images")
    new_parser.add_argument("catalog_dir")
    new_parser.add_argument("slug")
    new_parser.add_argument("--source", action="append", required=True, help="local reference image; repeat for multiple images")
    new_parser.set_defaults(func=cmd_new)

    render_parser = subparsers.add_parser("render", help="validate an entry and regenerate DESIGN.md")
    render_parser.add_argument("entry_dir")
    render_parser.set_defaults(func=cmd_render)

    reindex_parser = subparsers.add_parser("reindex", help="validate entries and regenerate catalog indexes")
    reindex_parser.add_argument("catalog_dir")
    reindex_parser.set_defaults(func=cmd_reindex)

    validate_parser = subparsers.add_parser("validate", help="validate a catalog or one entry without writing")
    validate_parser.add_argument("target")
    validate_parser.set_defaults(func=cmd_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except CatalogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"error: filesystem operation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
