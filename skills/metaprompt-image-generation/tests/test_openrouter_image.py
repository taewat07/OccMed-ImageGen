import base64
import importlib.util
import io
import json
import os
import stat
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock
from urllib.error import URLError

from PIL import Image

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "openrouter_image.py"
SPEC = importlib.util.spec_from_file_location("openrouter_image", SCRIPT_PATH)
assert SPEC and SPEC.loader
openrouter_image = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = openrouter_image
SPEC.loader.exec_module(openrouter_image)


def image_bytes(image_format="PNG", mode="RGB"):
    output = io.BytesIO()
    color = (20, 40, 60, 128) if mode == "RGBA" else (20, 40, 60)
    Image.new(mode, (4, 3), color).save(output, format=image_format)
    return output.getvalue()


class DotEnvTests(unittest.TestCase):
    def test_distributed_default_model_is_gpt_image_2(self):
        values = openrouter_image.parse_dotenv(openrouter_image.ENV_EXAMPLE_PATH)

        self.assertEqual(values["OPENROUTER_IMAGE_MODEL"], "openai/gpt-image-2")

    def test_process_environment_overrides_package_env(self):
        with tempfile.TemporaryDirectory() as temporary:
            env_path = Path(temporary) / ".env"
            env_path.write_text(
                "OPENROUTER_API_KEY=file-key\n"
                "OPENROUTER_IMAGE_MODEL='file/model'\n"
                "OPENROUTER_APP_TITLE=Package Image Skill # comment\n",
                encoding="utf-8",
            )
            config = openrouter_image.load_config(
                env_path,
                {
                    "OPENROUTER_API_KEY": "process-key",
                    "OPENROUTER_IMAGE_MODEL": "process/model",
                },
            )

        self.assertEqual(config.api_key, "process-key")
        self.assertEqual(config.image_model, "process/model")
        self.assertEqual(config.app_title, "Package Image Skill")

    def test_init_creates_private_env_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            example = root / ".env.example"
            target = root / ".env"
            example.write_text("OPENROUTER_API_KEY=\n", encoding="utf-8")
            result = openrouter_image.init_env(target, example)

            self.assertEqual(result["status"], "ok")
            self.assertTrue(target.exists())
            if os.name != "nt":
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
            with self.assertRaises(openrouter_image.ConfigError):
                openrouter_image.init_env(target, example)

    def test_secret_redaction(self):
        secret = "sk-or-v1-secret"
        text = f"Authorization: Bearer {secret}; OPENROUTER_API_KEY={secret}"
        redacted = openrouter_image.redact_secret(text, secret)
        self.assertNotIn(secret, redacted)
        self.assertIn("[REDACTED]", redacted)


class RequestTests(unittest.TestCase):
    def test_rejects_unknown_and_incompatible_fields(self):
        with self.assertRaisesRegex(openrouter_image.ConfigError, "Unsupported request fields"):
            openrouter_image.validate_request({"prompt": "x", "surprise": True})
        request = openrouter_image.validate_request(
            {"prompt": "x", "output_format": "png", "output_compression": 90}
        )
        self.assertEqual(request["output_compression"], 90)
        self.assertEqual(openrouter_image.validate_request({"prompt": "x"})["output_format"], "png")
        with self.assertRaisesRegex(openrouter_image.ConfigError, "png or jpeg"):
            openrouter_image.validate_request({"prompt": "x", "output_format": "webp"})

    def test_local_and_remote_references_are_normalized(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            local = root / "reference.png"
            local.write_bytes(b"png-bytes")
            references = openrouter_image.normalize_references(
                ["reference.png", "https://example.com/reference.jpg"], root
            )

        local_url = references[0]["image_url"]["url"]
        self.assertTrue(local_url.startswith("data:image/png;base64,"))
        self.assertEqual(
            references[1]["image_url"]["url"],
            "https://example.com/reference.jpg",
        )
        with self.assertRaises(openrouter_image.ConfigError):
            openrouter_image.normalize_references(
                ["http://example.com/reference.jpg"], root
            )

    def test_capability_validation_rejects_unsupported_parameter(self):
        model = {
            "architecture": {
                "input_modalities": ["text"],
                "output_modalities": ["image"],
            },
            "supported_parameters": {"resolution": {"type": "enum", "values": ["1K"]}},
        }
        with self.assertRaisesRegex(openrouter_image.ConfigError, "aspect_ratio"):
            openrouter_image.validate_capabilities(
                model, {"prompt": "x", "aspect_ratio": "1:1", "input_references": []}
            )

    def test_capability_validation_enforces_reference_limit(self):
        model = {
            "architecture": {
                "input_modalities": ["text", "image"],
                "output_modalities": ["image"],
            },
            "supported_parameters": {
                "input_references": {"type": "range", "min": 0, "max": 2}
            },
        }

        with self.assertRaisesRegex(openrouter_image.ConfigError, "input_references <= 2"):
            openrouter_image.validate_capabilities(
                model,
                {
                    "prompt": "x",
                    "input_references": ["a.png", "b.png", "c.png"],
                },
            )

    def test_delivery_format_is_forwarded_only_when_model_supports_it(self):
        request = {"output_format": "png", "output_compression": 85}
        unsupported = openrouter_image.provider_delivery_parameters({}, request)
        supported = openrouter_image.provider_delivery_parameters(
            {
                "output_format": {"type": "enum", "values": ["png", "jpeg"]},
                "output_compression": {"type": "range", "min": 0, "max": 100},
            },
            request,
        )
        provider_only_jpeg = openrouter_image.provider_delivery_parameters(
            {"output_format": {"type": "enum", "values": ["jpeg"]}}, request
        )

        self.assertEqual(unsupported, {})
        self.assertEqual(supported, {"output_format": "png", "output_compression": 85})
        self.assertEqual(provider_only_jpeg, {})


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.payload


class ClientRetryTests(unittest.TestCase):
    def setUp(self):
        self.config = openrouter_image.AppConfig(
            api_key="retry-secret",
            image_model="test/image-model",
            base_url="https://openrouter.ai/api/v1",
            app_title="Test",
            http_referer="",
        )

    def test_read_only_discovery_retries_network_failure(self):
        client = openrouter_image.OpenRouterClient(self.config, retries=1)
        response = FakeResponse({"data": []})
        with mock.patch.object(
            openrouter_image, "urlopen", side_effect=[URLError("offline"), response]
        ) as mocked_urlopen, mock.patch.object(openrouter_image.time, "sleep"):
            models = client.list_models()

        self.assertEqual(models, [])
        self.assertEqual(mocked_urlopen.call_count, 2)

    def test_paid_post_does_not_retry_ambiguous_network_failure(self):
        client = openrouter_image.OpenRouterClient(self.config, retries=2)
        with mock.patch.object(
            openrouter_image, "urlopen", side_effect=URLError("connection lost")
        ) as mocked_urlopen, mock.patch.object(openrouter_image.time, "sleep"):
            with self.assertRaises(openrouter_image.ApiError):
                client.generate({"model": "test/image-model", "prompt": "x"})

        self.assertEqual(mocked_urlopen.call_count, 1)


class FakeClient:
    def __init__(self, model, responses):
        self.model = model
        self.responses = list(responses)
        self.payloads = []

    def list_models(self):
        return [self.model]

    def get_key_info(self):
        return {"label": "test-key"}

    def generate(self, payload):
        self.payloads.append(dict(payload))
        return self.responses.pop(0)


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.config = openrouter_image.AppConfig(
            api_key="test-key",
            image_model="test/image-model",
            base_url="https://openrouter.ai/api/v1",
            app_title="Test",
            http_referer="",
        )

    def test_exact_count_falls_back_to_single_requests_without_n(self):
        encoded = base64.b64encode(image_bytes("PNG")).decode("ascii")
        model = {
            "id": "test/image-model",
            "architecture": {
                "input_modalities": ["text", "image"],
                "output_modalities": ["image"],
            },
            "supported_parameters": {},
        }
        response = {"data": [{"b64_json": encoded, "media_type": "image/png"}], "usage": {"cost": 0.01}}
        client = FakeClient(model, [response, response, response])

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = openrouter_image.generate_images(
                self.config,
                {"prompt": "three images", "count": 3, "output_dir": "out"},
                root,
                client=client,
                cwd=root,
            )
            files_exist = all(Path(path).is_file() for path in manifest["files"])

        self.assertEqual(manifest["count"], 3)
        self.assertEqual(manifest["request_count"], 3)
        self.assertEqual(manifest["usage"]["cost"], 0.03)
        self.assertTrue(files_exist)
        self.assertTrue(all("n" not in payload for payload in client.payloads))
        self.assertTrue(all("output_format" not in payload for payload in client.payloads))
        self.assertEqual(manifest["output_format"], "png")
        self.assertFalse(manifest["transcoded"])

    def test_batch_uses_n_when_model_supports_it(self):
        encoded = base64.b64encode(image_bytes("JPEG")).decode("ascii")
        model = {
            "id": "test/image-model",
            "architecture": {"input_modalities": ["text"], "output_modalities": ["image"]},
            "supported_parameters": {"n": {"type": "range", "min": 1, "max": 10}},
        }
        response = {
            "data": [
                {"b64_json": encoded, "media_type": "image/jpeg"},
                {"b64_json": encoded, "media_type": "image/jpeg"},
            ]
        }
        client = FakeClient(model, [response])

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = openrouter_image.generate_images(
                self.config,
                {"prompt": "two", "count": 2, "output_dir": "out"},
                root,
                client=client,
                cwd=root,
            )
            delivered_files = [Path(path).read_bytes() for path in manifest["files"]]

        self.assertEqual(manifest["count"], 2)
        self.assertEqual(client.payloads[0]["n"], 2)
        self.assertTrue(all(path.endswith(".png") for path in manifest["files"]))
        self.assertTrue(manifest["transcoded"])
        self.assertEqual(manifest["provider_formats"], ["image/jpeg", "image/jpeg"])
        self.assertTrue(all(content.startswith(b"\x89PNG") for content in delivered_files))

    def test_png_with_alpha_is_delivered_as_jpeg(self):
        encoded = base64.b64encode(image_bytes("PNG", "RGBA")).decode("ascii")
        model = {
            "id": "test/image-model",
            "architecture": {"input_modalities": ["text"], "output_modalities": ["image"]},
            "supported_parameters": {},
        }
        client = FakeClient(
            model, [{"data": [{"b64_json": encoded, "media_type": "image/png"}]}]
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = openrouter_image.generate_images(
                self.config,
                {
                    "prompt": "jpeg delivery",
                    "output_format": "jpeg",
                    "output_compression": 82,
                    "output_dir": "out",
                },
                root,
                client=client,
                cwd=root,
            )
            delivered = Path(manifest["files"][0]).read_bytes()

        self.assertTrue(manifest["files"][0].endswith(".jpg"))
        self.assertTrue(delivered.startswith(b"\xff\xd8\xff"))
        self.assertEqual(manifest["outputs"][0]["output_format"], "jpeg")
        self.assertTrue(manifest["outputs"][0]["transcoded"])

    def test_invalid_base64_is_output_error(self):
        model = {
            "id": "test/image-model",
            "architecture": {"input_modalities": ["text"], "output_modalities": ["image"]},
            "supported_parameters": {},
        }
        client = FakeClient(model, [{"data": [{"b64_json": "%%%"}]}])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(openrouter_image.OutputError):
                openrouter_image.generate_images(
                    self.config,
                    {"prompt": "x", "output_dir": "out"},
                    root,
                    client=client,
                    cwd=root,
                )

    def test_non_image_bytes_are_output_error(self):
        encoded = base64.b64encode(b"not an image").decode("ascii")
        model = {
            "id": "test/image-model",
            "architecture": {"input_modalities": ["text"], "output_modalities": ["image"]},
            "supported_parameters": {},
        }
        client = FakeClient(model, [{"data": [{"b64_json": encoded}]}])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(openrouter_image.OutputError):
                openrouter_image.generate_images(
                    self.config,
                    {"prompt": "x", "output_dir": "out"},
                    root,
                    client=client,
                    cwd=root,
                )

    def test_failed_later_batch_removes_partial_outputs(self):
        encoded = base64.b64encode(image_bytes("PNG")).decode("ascii")
        model = {
            "id": "test/image-model",
            "architecture": {"input_modalities": ["text"], "output_modalities": ["image"]},
            "supported_parameters": {},
        }
        client = FakeClient(
            model,
            [
                {"data": [{"b64_json": encoded, "media_type": "image/png"}]},
                {"data": [{"b64_json": "not-base64", "media_type": "image/png"}]},
            ],
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(openrouter_image.OutputError):
                openrouter_image.generate_images(
                    self.config,
                    {"prompt": "two images", "count": 2, "output_dir": "out"},
                    root,
                    client=client,
                    cwd=root,
                )
            remaining_files = list((root / "out").glob("*"))

        self.assertEqual(remaining_files, [])

    def test_doctor_validates_authentication_and_model(self):
        model = {
            "id": "test/image-model",
            "architecture": {"input_modalities": ["text"], "output_modalities": ["image"]},
            "supported_parameters": {"aspect_ratio": ["1:1", "3:4"]},
        }
        client = FakeClient(model, [])

        result = openrouter_image.doctor(self.config, client=client)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["model"], "test/image-model")
        self.assertIn("aspect_ratio", result["supported_parameters"])
        self.assertEqual(result["default_delivery_format"], "png")

    def test_doctor_rejects_missing_pillow(self):
        with mock.patch.object(openrouter_image, "PILImage", None):
            with self.assertRaisesRegex(openrouter_image.ConfigError, "Pillow is required"):
                openrouter_image.doctor(self.config, client=FakeClient({}, []))


class FixtureHandler(BaseHTTPRequestHandler):
    post_count = 0
    payloads = []

    def log_message(self, format, *args):
        return

    def do_GET(self):
        if self.path == "/api/v1/key":
            body = json.dumps({"data": {"is_free_tier": False}}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path != "/api/v1/images/models":
            self.send_error(404)
            return
        body = json.dumps(
            {
                "data": [
                    {
                        "id": "fixture/image-model",
                        "name": "Fixture",
                        "architecture": {
                            "input_modalities": ["text", "image"],
                            "output_modalities": ["image"],
                        },
                        "supported_parameters": {},
                    }
                ]
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path != "/api/v1/images":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        type(self).payloads.append(payload)
        type(self).post_count += 1
        encoded = base64.b64encode(image_bytes("PNG")).decode("ascii")
        body = json.dumps(
            {
                "data": [{"b64_json": encoded, "media_type": "image/png"}],
                "usage": {"cost": 0.005},
            }
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class CliIntegrationTests(unittest.TestCase):
    def test_offline_fixture_covers_discovery_generation_and_batching(self):
        FixtureHandler.post_count = 0
        FixtureHandler.payloads = []
        server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                request_path = root / "request.json"
                request_path.write_text(
                    json.dumps(
                        {
                            "prompt": "fixture prompt",
                            "count": 3,
                            "output_dir": "outputs",
                        }
                    ),
                    encoding="utf-8",
                )
                env = dict(os.environ)
                env.update(
                    {
                        "OPENROUTER_API_KEY": "fixture-secret",
                        "OPENROUTER_IMAGE_MODEL": "fixture/image-model",
                        "OPENROUTER_BASE_URL": f"http://127.0.0.1:{server.server_port}/api/v1",
                    }
                )
                result = subprocess.run(
                    [sys.executable, str(SCRIPT_PATH), "generate", "--request", str(request_path)],
                    cwd=root,
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                )
                manifest = json.loads(result.stdout)
                files_exist = all(Path(path).is_file() for path in manifest["files"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(manifest["count"], 3)
        self.assertEqual(FixtureHandler.post_count, 3)
        self.assertTrue(files_exist)
        self.assertEqual(manifest["output_format"], "png")
        self.assertFalse(manifest["transcoded"])
        self.assertNotIn("fixture-secret", result.stdout + result.stderr)


class CliExitCodeTests(unittest.TestCase):
    def setUp(self):
        self.config = openrouter_image.AppConfig(
            api_key="never-print-this-secret",
            image_model="test/image-model",
            base_url="https://openrouter.ai/api/v1",
            app_title="Test",
            http_referer="",
        )

    def _run_main(
        self,
        argv,
        load_config_side_effect=None,
        list_models_side_effect=None,
        key_info_side_effect=None,
    ):
        stderr = io.StringIO()
        load_patch = mock.patch.object(openrouter_image, "load_config")
        list_patch = mock.patch.object(openrouter_image.OpenRouterClient, "list_models")
        key_patch = mock.patch.object(openrouter_image.OpenRouterClient, "get_key_info")
        with load_patch as mocked_load, list_patch as mocked_models, key_patch as mocked_key_info, mock.patch.object(
            sys, "stderr", stderr
        ):
            if load_config_side_effect is None:
                mocked_load.return_value = self.config
            else:
                mocked_load.side_effect = load_config_side_effect
            if list_models_side_effect is not None:
                mocked_models.side_effect = list_models_side_effect
            if key_info_side_effect is not None:
                mocked_key_info.side_effect = key_info_side_effect
            else:
                mocked_key_info.return_value = {}
            code = openrouter_image.main(argv)
        return code, stderr.getvalue()

    def test_configuration_failure_uses_exit_2(self):
        code, stderr = self._run_main(
            ["doctor"],
            load_config_side_effect=openrouter_image.ConfigError("missing key"),
        )
        self.assertEqual(code, openrouter_image.EXIT_CONFIG)
        self.assertIn('"code": "configuration_error"', stderr)

    def test_api_failure_uses_exit_3_and_redacts_key(self):
        code, stderr = self._run_main(
            ["doctor"],
            key_info_side_effect=openrouter_image.ApiError(
                "Bearer never-print-this-secret"
            ),
        )
        self.assertEqual(code, openrouter_image.EXIT_API)
        self.assertIn('"code": "openrouter_error"', stderr)
        self.assertNotIn("never-print-this-secret", stderr)

    def test_output_failure_uses_exit_4(self):
        code, stderr = self._run_main(
            ["models"],
            list_models_side_effect=openrouter_image.OutputError("bad response"),
        )
        self.assertEqual(code, openrouter_image.EXIT_OUTPUT)
        self.assertIn('"code": "output_error"', stderr)


if __name__ == "__main__":
    unittest.main()
