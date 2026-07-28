#!/usr/bin/env python3
"""Portable OpenRouter Image API runner for the meta-prompt image skill."""

from __future__ import annotations

import argparse
import base64
import binascii
import io
import json
import mimetypes
import os
import re
import shlex
import stat
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

try:
    from PIL import Image as PILImage
    from PIL import UnidentifiedImageError
except ImportError:  # Keep init and --help usable before dependencies are installed.
    PILImage = None
    UnidentifiedImageError = OSError

EXIT_SUCCESS = 0
EXIT_CONFIG = 2
EXIT_API = 3
EXIT_OUTPUT = 4

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PACKAGE_ROOT / ".env"
ENV_EXAMPLE_PATH = PACKAGE_ROOT / ".env.example"
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_APP_TITLE = "Meta-Prompt Image Generation"
DEFAULT_OUTPUT_DIR = "generated-images"
MAX_IMAGES = 100
TRANSIENT_HTTP_STATUSES = {429, 500, 502, 503, 504}

KNOWN_ENV_KEYS = {
    "OPENROUTER_API_KEY",
    "OPENROUTER_IMAGE_MODEL",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_APP_TITLE",
    "OPENROUTER_HTTP_REFERER",
}

REQUEST_FIELDS = {
    "prompt",
    "model",
    "count",
    "aspect_ratio",
    "resolution",
    "quality",
    "output_format",
    "background",
    "output_compression",
    "seed",
    "input_references",
    "output_dir",
}

OPTIONAL_API_FIELDS = (
    "aspect_ratio",
    "resolution",
    "quality",
    "background",
    "seed",
)

FORMAT_EXTENSIONS = {
    "png": ".png",
    "jpeg": ".jpg",
}

PILLOW_REQUIREMENT = PACKAGE_ROOT / "requirements.txt"


class ConfigError(Exception):
    """Invalid local configuration or generation request."""


class ApiError(Exception):
    """OpenRouter or network request failed."""


class OutputError(Exception):
    """OpenRouter returned malformed output or a file could not be written."""


@dataclass(frozen=True)
class AppConfig:
    api_key: str
    image_model: str
    base_url: str
    app_title: str
    http_referer: str
    warnings: tuple[str, ...] = ()


def _parse_env_value(raw_value: str) -> str:
    lexer = shlex.shlex(raw_value, posix=True)
    lexer.whitespace_split = True
    lexer.commenters = "#"
    try:
        return " ".join(list(lexer))
    except ValueError as exc:
        raise ConfigError(f"Invalid .env value: {exc}") from exc


def parse_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    if not path.is_file():
        raise ConfigError(f"Configuration path is not a file: {path}")

    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigError(f"Unable to read configuration file: {path}") from exc

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            raise ConfigError(f"Invalid .env assignment on line {line_number}")
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise ConfigError(f"Invalid .env key on line {line_number}")
        values[key] = _parse_env_value(raw_value.strip())
    return values


def _env_permission_warning(path: Path) -> Optional[str]:
    if os.name == "nt" or not path.exists():
        return None
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError:
        return "Could not verify package .env permissions."
    if mode & 0o077:
        return "Package .env is readable by other users; run chmod 600 on it."
    return None


def _validate_base_url(value: str) -> str:
    base_url = value.rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme == "https" and parsed.netloc:
        return base_url
    if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
        return base_url
    raise ConfigError("OPENROUTER_BASE_URL must use HTTPS (HTTP is allowed only for localhost tests)")


def load_config(
    env_path: Path = ENV_PATH,
    environ: Optional[Mapping[str, str]] = None,
) -> AppConfig:
    file_values = parse_dotenv(env_path)
    process_values = os.environ if environ is None else environ

    merged: dict[str, str] = {}
    for key in KNOWN_ENV_KEYS:
        value = file_values.get(key, "")
        if key in process_values:
            value = str(process_values[key])
        merged[key] = value.strip()

    api_key = merged["OPENROUTER_API_KEY"]
    image_model = merged["OPENROUTER_IMAGE_MODEL"]
    if not api_key:
        raise ConfigError(
            "OPENROUTER_API_KEY is missing. Run the init command, then add the key to the package .env."
        )
    if not image_model:
        raise ConfigError("OPENROUTER_IMAGE_MODEL is missing from the package .env")

    warnings: list[str] = []
    permission_warning = _env_permission_warning(env_path)
    if permission_warning:
        warnings.append(permission_warning)

    return AppConfig(
        api_key=api_key,
        image_model=image_model,
        base_url=_validate_base_url(
            merged["OPENROUTER_BASE_URL"] or DEFAULT_BASE_URL
        ),
        app_title=merged["OPENROUTER_APP_TITLE"] or DEFAULT_APP_TITLE,
        http_referer=merged["OPENROUTER_HTTP_REFERER"],
        warnings=tuple(warnings),
    )


def init_env(
    env_path: Path = ENV_PATH,
    example_path: Path = ENV_EXAMPLE_PATH,
) -> dict[str, Any]:
    if env_path.exists():
        raise ConfigError(f"Refusing to overwrite existing configuration: {env_path}")
    if not example_path.is_file():
        raise ConfigError(f"Missing configuration template: {example_path}")
    try:
        content = example_path.read_text(encoding="utf-8")
        with env_path.open("x", encoding="utf-8") as handle:
            handle.write(content)
        if os.name != "nt":
            env_path.chmod(0o600)
    except OSError as exc:
        raise ConfigError(f"Unable to create package configuration: {env_path}") from exc
    return {
        "status": "ok",
        "env_file": str(env_path),
        "message": "Add your OpenRouter API key and preferred image model to this file.",
    }


def redact_secret(text: str, api_key: str = "") -> str:
    redacted = text
    if api_key:
        redacted = redacted.replace(api_key, "[REDACTED]")
    redacted = re.sub(
        r"(?i)Bearer\s+[A-Za-z0-9._~+\-/=]+",
        "Bearer [REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"(?i)(OPENROUTER_API_KEY\s*[=:]\s*)[^\s,}\]]+",
        r"\1[REDACTED]",
        redacted,
    )
    return redacted


class OpenRouterClient:
    def __init__(self, config: AppConfig, timeout: int = 180, retries: int = 2):
        self.config = config
        self.timeout = timeout
        self.retries = retries

    def _headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "X-OpenRouter-Title": self.config.app_title,
        }
        if self.config.http_referer:
            headers["HTTP-Referer"] = self.config.http_referer
        return headers

    def _request_json(
        self,
        method: str,
        path: str,
        payload: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        url = f"{self.config.base_url}{path}"
        body = None
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        for attempt in range(self.retries + 1):
            request = Request(url, data=body, headers=self._headers(), method=method)
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    raw = response.read()
                try:
                    decoded = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise OutputError("OpenRouter returned a non-JSON response") from exc
                if not isinstance(decoded, dict):
                    raise OutputError("OpenRouter returned an invalid JSON response")
                return decoded
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                safe_detail = redact_secret(detail, self.config.api_key)
                if exc.code in TRANSIENT_HTTP_STATUSES and attempt < self.retries:
                    time.sleep(min(2**attempt, 4))
                    continue
                raise ApiError(
                    f"OpenRouter request failed with HTTP {exc.code}: {safe_detail}"
                ) from exc
            except URLError as exc:
                # Retry read-only discovery. A timed-out paid POST may have reached the provider.
                if method == "GET" and attempt < self.retries:
                    time.sleep(min(2**attempt, 4))
                    continue
                safe_reason = redact_secret(str(exc.reason), self.config.api_key)
                raise ApiError(f"OpenRouter network request failed: {safe_reason}") from exc
            except TimeoutError as exc:
                if method == "GET" and attempt < self.retries:
                    time.sleep(min(2**attempt, 4))
                    continue
                raise ApiError("OpenRouter request timed out") from exc
        raise ApiError("OpenRouter request failed after retries")

    def list_models(self) -> list[dict[str, Any]]:
        response = self._request_json("GET", "/images/models")
        models = response.get("data")
        if not isinstance(models, list):
            raise OutputError("OpenRouter model discovery response is missing data")
        return [model for model in models if isinstance(model, dict)]

    def get_key_info(self) -> dict[str, Any]:
        response = self._request_json("GET", "/key")
        key_info = response.get("data")
        if not isinstance(key_info, dict):
            raise OutputError("OpenRouter key validation response is missing data")
        return key_info

    def generate(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        return self._request_json("POST", "/images", payload)


def find_model(models: Iterable[Mapping[str, Any]], model_id: str) -> dict[str, Any]:
    for model in models:
        if model.get("id") == model_id:
            return dict(model)
    raise ConfigError(f"Configured OpenRouter image model was not found: {model_id}")


def _require_string(request: Mapping[str, Any], key: str) -> str:
    value = request.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"Request field '{key}' must be a non-empty string")
    return value.strip()


def validate_request(raw_request: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw_request, Mapping):
        raise ConfigError("Request JSON must contain an object")
    unknown = sorted(set(raw_request) - REQUEST_FIELDS)
    if unknown:
        raise ConfigError(f"Unsupported request fields: {', '.join(unknown)}")

    request = dict(raw_request)
    request["prompt"] = _require_string(request, "prompt")

    model = request.get("model")
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise ConfigError("Request field 'model' must be a non-empty string")
    if isinstance(model, str):
        request["model"] = model.strip()

    count = request.get("count", 1)
    if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= MAX_IMAGES:
        raise ConfigError(f"Request field 'count' must be an integer from 1 to {MAX_IMAGES}")
    request["count"] = count

    for key in ("aspect_ratio", "resolution", "quality", "output_format", "background"):
        value = request.get(key)
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ConfigError(f"Request field '{key}' must be a non-empty string")
        if isinstance(value, str):
            request[key] = value.strip()

    aspect_ratio = request.get("aspect_ratio")
    if aspect_ratio and aspect_ratio != "auto" and not re.fullmatch(r"[1-9]\d*:[1-9]\d*", aspect_ratio):
        raise ConfigError("Request field 'aspect_ratio' must be 'auto' or a positive W:H ratio")

    quality = request.get("quality")
    if quality and quality not in {"auto", "low", "medium", "high"}:
        raise ConfigError("Request field 'quality' must be auto, low, medium, or high")

    output_format = request.get("output_format", "png")
    if output_format and output_format not in FORMAT_EXTENSIONS:
        raise ConfigError("Request field 'output_format' must be png or jpeg")
    request["output_format"] = output_format

    background = request.get("background")
    if background and background not in {"auto", "transparent", "opaque"}:
        raise ConfigError("Request field 'background' must be auto, transparent, or opaque")
    if background == "transparent" and output_format != "png":
        raise ConfigError("Transparent background requires PNG output")

    compression = request.get("output_compression")
    if compression is not None:
        if isinstance(compression, bool) or not isinstance(compression, int) or not 0 <= compression <= 100:
            raise ConfigError("Request field 'output_compression' must be an integer from 0 to 100")

    seed = request.get("seed")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise ConfigError("Request field 'seed' must be an integer")

    references = request.get("input_references", [])
    if references is None:
        references = []
    if not isinstance(references, list) or any(
        not isinstance(item, str) or not item.strip() for item in references
    ):
        raise ConfigError("Request field 'input_references' must be a list of paths or URLs")
    request["input_references"] = [item.strip() for item in references]

    output_dir = request.get("output_dir", DEFAULT_OUTPUT_DIR)
    if not isinstance(output_dir, str) or not output_dir.strip():
        raise ConfigError("Request field 'output_dir' must be a non-empty path")
    request["output_dir"] = output_dir.strip()
    return request


def _validate_descriptor(key: str, value: Any, descriptor: Any) -> None:
    if not isinstance(descriptor, Mapping):
        return
    descriptor_type = descriptor.get("type")
    if descriptor_type == "enum":
        values = descriptor.get("values")
        if isinstance(values, list) and value not in values:
            rendered = ", ".join(str(item) for item in values)
            raise ConfigError(f"Model does not accept {key}={value}; allowed values: {rendered}")
    elif descriptor_type == "range":
        minimum = descriptor.get("min")
        maximum = descriptor.get("max")
        if isinstance(minimum, (int, float)) and value < minimum:
            raise ConfigError(f"Model requires {key} >= {minimum}")
        if isinstance(maximum, (int, float)) and value > maximum:
            raise ConfigError(f"Model requires {key} <= {maximum}")


def validate_capabilities(model: Mapping[str, Any], request: Mapping[str, Any]) -> dict[str, Any]:
    architecture = model.get("architecture")
    if isinstance(architecture, Mapping):
        outputs = architecture.get("output_modalities")
        if isinstance(outputs, list) and "image" not in outputs:
            raise ConfigError("Configured model does not declare image output capability")
        inputs = architecture.get("input_modalities")
        if request.get("input_references") and isinstance(inputs, list) and "image" not in inputs:
            raise ConfigError("Configured model does not accept image references")

    supported = model.get("supported_parameters")
    if not isinstance(supported, Mapping):
        supported = {}

    references = request.get("input_references", [])
    if references:
        descriptor = supported.get("input_references")
        if descriptor is None:
            raise ConfigError("Configured model does not support input references")
        _validate_descriptor("input_references", len(references), descriptor)

    for key in OPTIONAL_API_FIELDS:
        if key not in request:
            continue
        if key not in supported:
            raise ConfigError(f"Configured model does not support request parameter: {key}")
        _validate_descriptor(key, request[key], supported[key])
    return dict(supported)


def provider_delivery_parameters(
    supported: Mapping[str, Any], request: Mapping[str, Any]
) -> dict[str, Any]:
    """Return delivery controls that the selected OpenRouter model explicitly accepts."""
    output_format = request["output_format"]
    format_descriptor = supported.get("output_format")
    if format_descriptor is None:
        return {}
    try:
        _validate_descriptor("output_format", output_format, format_descriptor)
    except ConfigError:
        # Let the provider return its native raster; local delivery conversion is authoritative.
        return {}

    parameters: dict[str, Any] = {"output_format": output_format}
    compression = request.get("output_compression")
    compression_descriptor = supported.get("output_compression")
    if compression is not None and compression_descriptor is not None:
        try:
            _validate_descriptor("output_compression", compression, compression_descriptor)
        except ConfigError:
            pass
        else:
            parameters["output_compression"] = compression
    return parameters


def _reference_to_data_url(path: Path) -> str:
    if not path.is_file():
        raise ConfigError(f"Reference image does not exist or is not a file: {path}")
    mime_type, _ = mimetypes.guess_type(path.name)
    if not mime_type or not mime_type.startswith("image/"):
        raise ConfigError(f"Reference file does not have a recognized image type: {path}")
    try:
        encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    except OSError as exc:
        raise ConfigError(f"Unable to read reference image: {path}") from exc
    return f"data:{mime_type};base64,{encoded}"


def normalize_references(values: Sequence[str], request_dir: Path) -> list[dict[str, Any]]:
    references: list[dict[str, Any]] = []
    for value in values:
        parsed = urlparse(value)
        if parsed.scheme == "https":
            url = value
        elif parsed.scheme == "http":
            raise ConfigError("Remote reference images must use HTTPS")
        elif parsed.scheme == "data":
            if not value.startswith("data:image/"):
                raise ConfigError("Only image data URLs are accepted as references")
            url = value
        elif parsed.scheme:
            raise ConfigError(f"Unsupported reference URL scheme: {parsed.scheme}")
        else:
            source_path = Path(value).expanduser()
            if not source_path.is_absolute():
                source_path = request_dir / source_path
            url = _reference_to_data_url(source_path.resolve())
        references.append(
            {"type": "image_url", "image_url": {"url": url}}
        )
    return references


def _resolve_output_dir(value: str, cwd: Path = Path.cwd()) -> Path:
    output_dir = Path(value).expanduser()
    if not output_dir.is_absolute():
        output_dir = cwd / output_dir
    resolved = output_dir.resolve()
    try:
        resolved.relative_to(PACKAGE_ROOT.resolve())
    except ValueError:
        pass
    else:
        raise ConfigError("Generated images must be written outside the installed skill package")
    return resolved


def _decode_image(item: Mapping[str, Any]) -> bytes:
    encoded = item.get("b64_json")
    if not isinstance(encoded, str) or not encoded:
        raise OutputError("OpenRouter image response is missing b64_json")
    try:
        return base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise OutputError("OpenRouter image response contains invalid base64") from exc


def ensure_image_runtime() -> None:
    if PILImage is None:
        raise ConfigError(
            "Pillow is required for guaranteed PNG/JPEG delivery. Install package dependencies with: "
            f"python3 -m pip install -r {PILLOW_REQUIREMENT}"
        )


def _provider_media_type(image_format: Optional[str]) -> str:
    if not image_format:
        return "application/octet-stream"
    normalized = image_format.upper()
    return {
        "PNG": "image/png",
        "JPEG": "image/jpeg",
        "JPG": "image/jpeg",
        "WEBP": "image/webp",
    }.get(normalized, f"image/{normalized.lower()}")


def _jpeg_ready(image: Any) -> Any:
    if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = PILImage.new("RGB", rgba.size, (255, 255, 255))
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return image.convert("RGB")


def _deliver_image(
    content: bytes,
    output_format: str,
    output_compression: Optional[int],
) -> tuple[bytes, str, bool]:
    ensure_image_runtime()
    try:
        with PILImage.open(io.BytesIO(content)) as image:
            image.load()
            source_format = (image.format or "").upper()
            provider_format = _provider_media_type(source_format)
            target_format = "JPEG" if output_format == "jpeg" else "PNG"
            reencode = source_format != target_format or (
                target_format == "JPEG" and output_compression is not None
            )
            if not reencode:
                return content, provider_format, False

            rendered = io.BytesIO()
            save_kwargs: dict[str, Any] = {}
            icc_profile = image.info.get("icc_profile")
            if icc_profile:
                save_kwargs["icc_profile"] = icc_profile
            if target_format == "JPEG":
                image = _jpeg_ready(image)
                save_kwargs["quality"] = output_compression if output_compression is not None else 90
                save_kwargs["optimize"] = True
            elif image.mode not in {"1", "L", "LA", "P", "RGB", "RGBA", "I"}:
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            image.save(rendered, format=target_format, **save_kwargs)
            delivered = rendered.getvalue()
            if not delivered:
                raise OutputError("Image conversion produced an empty file")
            return delivered, provider_format, True
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise OutputError("OpenRouter returned image bytes that Pillow could not decode") from exc


def _write_image(path: Path, content: bytes) -> None:
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_bytes(content)
        os.replace(temporary, path)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise OutputError(f"Unable to write generated image: {path}") from exc


def _batch_size(supported: Mapping[str, Any], remaining: int) -> int:
    descriptor = supported.get("n")
    if descriptor is None:
        return 1
    maximum = 10
    if isinstance(descriptor, Mapping):
        if descriptor.get("type") == "range" and isinstance(descriptor.get("max"), int):
            maximum = min(maximum, descriptor["max"])
        if descriptor.get("type") == "enum" and isinstance(descriptor.get("values"), list):
            numeric = [item for item in descriptor["values"] if isinstance(item, int)]
            if numeric:
                maximum = min(maximum, max(numeric))
    return max(1, min(remaining, maximum))


def _aggregate_usage(usages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    aggregate: dict[str, Any] = {"requests": len(usages)}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "cost"):
        values = [usage.get(key) for usage in usages]
        numeric = [value for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
        if numeric:
            aggregate[key] = sum(numeric)
    return aggregate


def generate_images(
    config: AppConfig,
    request: Mapping[str, Any],
    request_dir: Path,
    client: Optional[OpenRouterClient] = None,
    cwd: Optional[Path] = None,
) -> dict[str, Any]:
    ensure_image_runtime()
    validated = validate_request(request)
    selected_model = validated.get("model") or config.image_model
    api = client or OpenRouterClient(config)
    model = find_model(api.list_models(), selected_model)
    supported = validate_capabilities(model, validated)

    references = normalize_references(validated["input_references"], request_dir)
    output_dir = _resolve_output_dir(validated["output_dir"], cwd or Path.cwd())

    base_payload: dict[str, Any] = {
        "model": selected_model,
        "prompt": validated["prompt"],
    }
    for key in OPTIONAL_API_FIELDS:
        if key in validated:
            base_payload[key] = validated[key]
    base_payload.update(provider_delivery_parameters(supported, validated))
    if references:
        base_payload["input_references"] = references

    target_count = validated["count"]
    saved_files: list[str] = []
    outputs: list[dict[str, Any]] = []
    usages: list[Mapping[str, Any]] = []
    request_count = 0
    run_id = uuid.uuid4().hex[:8]
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    try:
        while len(saved_files) < target_count:
            remaining = target_count - len(saved_files)
            batch_size = _batch_size(supported, remaining)
            payload = dict(base_payload)
            if batch_size > 1:
                payload["n"] = batch_size

            response = api.generate(payload)
            request_count += 1
            data = response.get("data")
            if not isinstance(data, list) or not data:
                raise OutputError("OpenRouter image response contains no generated images")
            usage = response.get("usage")
            if isinstance(usage, Mapping):
                usages.append(usage)

            for item in data:
                if len(saved_files) >= target_count:
                    break
                if not isinstance(item, Mapping):
                    raise OutputError("OpenRouter image response contains an invalid image item")
                image_bytes = _decode_image(item)
                delivered_bytes, provider_format, transcoded = _deliver_image(
                    image_bytes,
                    validated["output_format"],
                    validated.get("output_compression"),
                )
                extension = FORMAT_EXTENSIONS[validated["output_format"]]
                index = len(saved_files) + 1
                output_path = output_dir / f"openrouter-{timestamp}-{run_id}-{index:03d}{extension}"
                _write_image(output_path, delivered_bytes)
                saved_files.append(str(output_path))
                outputs.append(
                    {
                        "path": str(output_path),
                        "provider_format": provider_format,
                        "reported_media_type": item.get("media_type"),
                        "output_format": validated["output_format"],
                        "transcoded": transcoded,
                    }
                )
    except (ApiError, OutputError):
        for saved_file in saved_files:
            try:
                Path(saved_file).unlink()
            except OSError:
                pass
        raise

    effective_parameters = {
        key: base_payload[key]
        for key in OPTIONAL_API_FIELDS
        if key in base_payload
    }
    effective_parameters["count"] = target_count
    effective_parameters["output_format"] = validated["output_format"]
    if "output_compression" in validated:
        effective_parameters["output_compression"] = validated["output_compression"]
    return {
        "status": "ok",
        "model": selected_model,
        "count": len(saved_files),
        "files": saved_files,
        "outputs": outputs,
        "output_format": validated["output_format"],
        "provider_formats": [output["provider_format"] for output in outputs],
        "transcoded": any(output["transcoded"] for output in outputs),
        "parameters": effective_parameters,
        "usage": _aggregate_usage(usages),
        "request_count": request_count,
        "warnings": list(config.warnings),
    }


def load_request_file(path_value: str) -> tuple[dict[str, Any], Path]:
    request_path = Path(path_value).expanduser().resolve()
    if not request_path.is_file():
        raise ConfigError(f"Request JSON does not exist: {request_path}")
    try:
        raw = json.loads(request_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ConfigError(f"Unable to read request JSON: {request_path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigError(f"Invalid request JSON: {exc.msg}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("Request JSON must contain an object")
    return raw, request_path.parent


def normalized_models(models: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for model in models:
        architecture = model.get("architecture")
        outputs = architecture.get("output_modalities", []) if isinstance(architecture, Mapping) else []
        if isinstance(outputs, list) and outputs and "image" not in outputs:
            continue
        normalized.append(
            {
                "id": model.get("id"),
                "name": model.get("name"),
                "input_modalities": architecture.get("input_modalities", [])
                if isinstance(architecture, Mapping)
                else [],
                "output_modalities": outputs,
                "supported_parameters": model.get("supported_parameters", {}),
                "supports_streaming": bool(model.get("supports_streaming", False)),
            }
        )
    return normalized


def doctor(config: AppConfig, client: Optional[OpenRouterClient] = None) -> dict[str, Any]:
    ensure_image_runtime()
    api = client or OpenRouterClient(config)
    api.get_key_info()
    model = find_model(api.list_models(), config.image_model)
    architecture = model.get("architecture")
    outputs = architecture.get("output_modalities", []) if isinstance(architecture, Mapping) else []
    if isinstance(outputs, list) and "image" not in outputs:
        raise ConfigError("Configured model does not declare image output capability")
    return {
        "status": "ok",
        "api": f"{config.base_url}/images",
        "model": config.image_model,
        "input_modalities": architecture.get("input_modalities", [])
        if isinstance(architecture, Mapping)
        else [],
        "supported_parameters": model.get("supported_parameters", {}),
        "warnings": list(config.warnings),
        "delivery_formats": ["png", "jpeg"],
        "default_delivery_format": "png",
        "message": "Configuration, Pillow, and model discovery succeeded. No image was generated.",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate images through OpenRouter's dedicated Image API."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init", help="Create a private package-local .env file")
    subparsers.add_parser("doctor", help="Validate credentials and selected model without generation")
    subparsers.add_parser("models", help="List image-capable OpenRouter models as JSON")
    generate_parser = subparsers.add_parser("generate", help="Generate images from a JSON request")
    generate_parser.add_argument("--request", required=True, help="Path to the request JSON file")
    return parser


def _emit(payload: Mapping[str, Any], stream: Any = sys.stdout) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=stream)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "init":
            _emit(init_env())
            return EXIT_SUCCESS

        config = load_config()
        client = OpenRouterClient(config)
        if args.command == "doctor":
            _emit(doctor(config, client))
        elif args.command == "models":
            models = normalized_models(client.list_models())
            _emit({"status": "ok", "count": len(models), "models": models})
        elif args.command == "generate":
            request, request_dir = load_request_file(args.request)
            _emit(generate_images(config, request, request_dir, client=client))
        return EXIT_SUCCESS
    except ConfigError as exc:
        _emit({"status": "error", "code": "configuration_error", "message": str(exc)}, sys.stderr)
        return EXIT_CONFIG
    except ApiError as exc:
        message = redact_secret(str(exc), locals().get("config", AppConfig("", "", "", "", "")).api_key)
        _emit({"status": "error", "code": "openrouter_error", "message": message}, sys.stderr)
        return EXIT_API
    except OutputError as exc:
        _emit({"status": "error", "code": "output_error", "message": str(exc)}, sys.stderr)
        return EXIT_OUTPUT


if __name__ == "__main__":
    raise SystemExit(main())
