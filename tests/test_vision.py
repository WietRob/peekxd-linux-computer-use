"""Tests for the peekxd vision module."""

import base64
import json
import os
import tempfile
from pathlib import Path
import unittest
from abc import ABC
from unittest.mock import MagicMock, patch, mock_open

from peekxd.core.errors import ProviderNotAvailableError, VisionError
from peekxd.vision.base import VisionProvider
from peekxd.vision.openai import OpenAIVisionProvider, _encode_image
from peekxd.vision.anthropic import AnthropicVisionProvider, _encode_image as _anthropic_encode_image
from peekxd.vision.ollama import OllamaVisionProvider, _encode_image as _ollama_encode_image
from peekxd.vision.hermes import HermesVisionProvider
from peekxd.vision.detector import get_vision_provider


class DummyVisionProvider(VisionProvider):
    """Concrete implementation of VisionProvider for testing the base class."""

    def __init__(self, available=True):
        self._available = available

    def analyze(self, image_path: str, prompt: str) -> str:
        return "dummy-result"

    def find_element(self, image_path: str, description: str):
        return (10, 20)

    def answer_question(self, image_path: str, question: str) -> str:
        return "dummy-answer"

    @property
    def name(self) -> str:
        return "dummy"

    @property
    def available(self) -> bool:
        return self._available


class TestVisionProviderBase(unittest.TestCase):
    """Test the abstract base class."""

    def test_cannot_instantiate_abstract(self):
        """VisionProvider is abstract and cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            VisionProvider()

    def test_dummy_provider(self):
        """A concrete subclass can be instantiated and used."""
        provider = DummyVisionProvider()
        self.assertEqual(provider.name, "dummy")
        self.assertTrue(provider.available)
        self.assertEqual(provider.analyze("img.png", "prompt"), "dummy-result")
        self.assertEqual(provider.find_element("img.png", "desc"), (10, 20))
        self.assertEqual(provider.answer_question("img.png", "q"), "dummy-answer")


class TestEncodeImage(unittest.TestCase):
    """Test image encoding utilities."""

    def test_encode_image_png(self):
        """_encode_image produces a data URL for PNG files."""
        png_data = b"\x89PNG\r\n\x1a\nfake"
        with patch("builtins.open", mock_open(read_data=png_data)):
            result = _encode_image("/tmp/test.png")
        self.assertTrue(result.startswith("data:image/png;base64,"))
        encoded = result.split(",")[1]
        self.assertEqual(base64.b64decode(encoded), png_data)

    def test_encode_image_jpg(self):
        """_encode_image produces a data URL for JPEG files."""
        jpg_data = b"\xff\xd8\xfffake"
        with patch("builtins.open", mock_open(read_data=jpg_data)):
            result = _encode_image("/tmp/test.jpg")
        self.assertTrue(result.startswith("data:image/jpeg;base64,"))


class TestOpenAIVisionProvider(unittest.TestCase):
    """Test OpenAI vision provider."""

    def setUp(self):
        self.provider = OpenAIVisionProvider()

    def tearDown(self):
        # Clean up cached client
        self.provider._client = None

    def test_name(self):
        self.assertEqual(self.provider.name, "openai")

    def test_default_model(self):
        self.assertEqual(self.provider.model, "gpt-4o")

    @patch.dict(os.environ, {"OPENAI_VISION_MODEL": "gpt-4o-mini"}, clear=False)
    def test_model_from_env(self):
        provider = OpenAIVisionProvider()
        self.assertEqual(provider.model, "gpt-4o-mini")

    def test_model_from_arg(self):
        provider = OpenAIVisionProvider(model="custom-model")
        self.assertEqual(provider.model, "custom-model")

    @patch.dict(os.environ, {}, clear=True)
    def test_available_no_key(self):
        self.assertFalse(self.provider.available)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True)
    def test_available_with_key_no_package(self):
        """When key is present but package is not installed, available is False."""
        provider = OpenAIVisionProvider()
        real_import = __import__

        def import_without_openai(name, *args, **kwargs):
            if name == "openai":
                raise ImportError("openai missing")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=import_without_openai):
            self.assertFalse(provider.available)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True)
    def test_analyze_success(self):
        """ analyze returns the assistant's message content."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Analysis result"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIVisionProvider()
        provider._client = mock_client

        with patch("peekxd.vision.openai._encode_image", return_value="data:image/png;base64,abc"):
            result = provider.analyze("/tmp/img.png", "Describe this")

        self.assertEqual(result, "Analysis result")
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args
        self.assertEqual(call_args.kwargs["model"], "gpt-4o")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True)
    def test_analyze_api_error(self):
        """analyze wraps API errors in VisionError."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API down")

        provider = OpenAIVisionProvider()
        provider._client = mock_client

        with patch("peekxd.vision.openai._encode_image", return_value="data:image/png;base64,abc"):
            with self.assertRaises(VisionError) as ctx:
                provider.analyze("/tmp/img.png", "Describe this")
        self.assertIn("OpenAI vision analysis failed", str(ctx.exception))

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True)
    def test_find_element_success(self):
        """find_element parses JSON coordinates."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"x": 150, "y": 250}'

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIVisionProvider()
        provider._client = mock_client

        with patch("peekxd.vision.openai._encode_image", return_value="data:image/png;base64,abc"):
            result = provider.find_element("/tmp/img.png", "a blue button")

        self.assertEqual(result, (150, 250))

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True)
    def test_find_element_not_found(self):
        """find_element returns None when coordinates are negative."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"x": -1, "y": -1}'

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIVisionProvider()
        provider._client = mock_client

        with patch("peekxd.vision.openai._encode_image", return_value="data:image/png;base64,abc"):
            result = provider.find_element("/tmp/img.png", "nonexistent thing")

        self.assertIsNone(result)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True)
    def test_find_element_markdown_code_block(self):
        """find_element strips markdown fences before parsing JSON."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '```json\n{"x": 42, "y": 99}\n```'

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIVisionProvider()
        provider._client = mock_client

        with patch("peekxd.vision.openai._encode_image", return_value="data:image/png;base64,abc"):
            result = provider.find_element("/tmp/img.png", "item")

        self.assertEqual(result, (42, 99))

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True)
    def test_find_element_bad_json(self):
        """find_element raises VisionError on unparseable JSON."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not json"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIVisionProvider()
        provider._client = mock_client

        with patch("peekxd.vision.openai._encode_image", return_value="data:image/png;base64,abc"):
            with self.assertRaises(VisionError):
                provider.find_element("/tmp/img.png", "item")

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True)
    def test_answer_question(self):
        """answer_question delegates to analyze."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Yes, it is."

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        provider = OpenAIVisionProvider()
        provider._client = mock_client

        with patch("peekxd.vision.openai._encode_image", return_value="data:image/png;base64,abc"):
            result = provider.answer_question("/tmp/img.png", "Is this a test?")

        self.assertEqual(result, "Yes, it is.")


class TestAnthropicVisionProvider(unittest.TestCase):
    """Test Anthropic vision provider."""

    def setUp(self):
        self.provider = AnthropicVisionProvider()

    def tearDown(self):
        self.provider._client = None

    def test_name(self):
        self.assertEqual(self.provider.name, "anthropic")

    def test_default_model(self):
        self.assertEqual(self.provider.model, "claude-3-opus-latest")

    @patch.dict(os.environ, {"ANTHROPIC_VISION_MODEL": "claude-3-sonnet"}, clear=False)
    def test_model_from_env(self):
        provider = AnthropicVisionProvider()
        self.assertEqual(provider.model, "claude-3-sonnet")

    def test_model_from_arg(self):
        provider = AnthropicVisionProvider(model="custom-claude")
        self.assertEqual(provider.model, "custom-claude")

    @patch.dict(os.environ, {}, clear=True)
    def test_available_no_key(self):
        self.assertFalse(self.provider.available)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True)
    def test_analyze_success(self):
        """analyze returns the content text."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Claude says hello")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        provider = AnthropicVisionProvider()
        provider._client = mock_client

        with patch("peekxd.vision.anthropic._encode_image", return_value="base64data"):
            result = provider.analyze("/tmp/img.png", "Describe this")

        self.assertEqual(result, "Claude says hello")
        mock_client.messages.create.assert_called_once()
        call_args = mock_client.messages.create.call_args
        self.assertEqual(call_args.kwargs["model"], "claude-3-opus-latest")
        self.assertEqual(call_args.kwargs["max_tokens"], 4096)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True)
    def test_analyze_api_error(self):
        """analyze wraps API errors in VisionError."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = RuntimeError("API down")

        provider = AnthropicVisionProvider()
        provider._client = mock_client

        with patch("peekxd.vision.anthropic._encode_image", return_value="base64data"):
            with self.assertRaises(VisionError) as ctx:
                provider.analyze("/tmp/img.png", "Describe this")
        self.assertIn("Anthropic vision analysis failed", str(ctx.exception))

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True)
    def test_find_element_success(self):
        """find_element parses JSON coordinates from Claude response."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"x": 300, "y": 400}')]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        provider = AnthropicVisionProvider()
        provider._client = mock_client

        with patch("peekxd.vision.anthropic._encode_image", return_value="base64data"):
            result = provider.find_element("/tmp/img.png", "the submit button")

        self.assertEqual(result, (300, 400))

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True)
    def test_find_element_not_found(self):
        """find_element returns None for negative coordinates."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"x": -1, "y": -1}')]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        provider = AnthropicVisionProvider()
        provider._client = mock_client

        with patch("peekxd.vision.anthropic._encode_image", return_value="base64data"):
            result = provider.find_element("/tmp/img.png", "nonexistent")

        self.assertIsNone(result)

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test"}, clear=True)
    def test_answer_question(self):
        """answer_question delegates to analyze."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="The answer is 42.")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response

        provider = AnthropicVisionProvider()
        provider._client = mock_client

        with patch("peekxd.vision.anthropic._encode_image", return_value="base64data"):
            result = provider.answer_question("/tmp/img.png", "What is the answer?")

        self.assertEqual(result, "The answer is 42.")


class TestOllamaVisionProvider(unittest.TestCase):
    """Test Ollama vision provider."""

    def setUp(self):
        self.provider = OllamaVisionProvider()

    def test_name(self):
        self.assertEqual(self.provider.name, "ollama")

    def test_default_model(self):
        self.assertEqual(self.provider.model, "llava")

    def test_default_host(self):
        self.assertEqual(self.provider.host, "http://localhost:11434")

    @patch.dict(os.environ, {"OLLAMA_HOST": "http://192.168.1.5:11434"}, clear=True)
    def test_host_from_env(self):
        provider = OllamaVisionProvider()
        self.assertEqual(provider.host, "http://192.168.1.5:11434")

    def test_host_from_arg(self):
        provider = OllamaVisionProvider(host="http://custom:8080")
        self.assertEqual(provider.host, "http://custom:8080")

    @patch.dict(os.environ, {"OLLAMA_HOST": "http://host-with-slash/"}, clear=True)
    def test_host_trailing_slash_stripped(self):
        provider = OllamaVisionProvider()
        self.assertEqual(provider.host, "http://host-with-slash")

    @patch.dict(os.environ, {"OLLAMA_VISION_MODEL": "llava-phi3"}, clear=True)
    def test_model_from_env(self):
        provider = OllamaVisionProvider()
        self.assertEqual(provider.model, "llava-phi3")

    @patch("requests.post")
    @patch("requests.get")
    def test_available_success(self, mock_get, mock_post):
        """available returns True when /api/tags responds 200."""
        mock_get.return_value = MagicMock(status_code=200)
        with patch.dict(os.environ, {}, clear=True):
            provider = OllamaVisionProvider()
            self.assertTrue(provider.available)
        mock_get.assert_called_once_with("http://localhost:11434/api/tags", timeout=2)

    @patch("requests.get", side_effect=Exception("Connection refused"))
    def test_available_failure(self, mock_get):
        """available returns False on connection error."""
        with patch.dict(os.environ, {}, clear=True):
            provider = OllamaVisionProvider()
            self.assertFalse(provider.available)

    @patch("requests.post")
    def test_analyze_success(self, mock_post):
        """analyze returns the response text."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"response": "This is a cat."},
            raise_for_status=lambda: None,
        )

        with patch.dict(os.environ, {}, clear=True):
            provider = OllamaVisionProvider()
            with patch("peekxd.vision.ollama._encode_image", return_value="base64img"):
                result = provider.analyze("/tmp/img.png", "What is this?")

        self.assertEqual(result, "This is a cat.")
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "http://localhost:11434/api/generate")
        self.assertEqual(call_args[1]["json"]["model"], "llava")
        self.assertEqual(call_args[1]["json"]["prompt"], "What is this?")
        self.assertEqual(call_args[1]["json"]["images"], ["base64img"])
        self.assertFalse(call_args[1]["json"]["stream"])

    @patch("requests.post", side_effect=Exception("Connection refused"))
    def test_analyze_connection_error(self, mock_post):
        """analyze wraps connection errors in VisionError."""
        with patch.dict(os.environ, {}, clear=True):
            provider = OllamaVisionProvider()
            with patch("peekxd.vision.ollama._encode_image", return_value="base64img"):
                with self.assertRaises(VisionError) as ctx:
                    provider.analyze("/tmp/img.png", "What?")
        self.assertIn("Ollama vision analysis failed", str(ctx.exception))

    @patch("requests.post")
    def test_find_element_success(self, mock_post):
        """find_element parses JSON coordinates."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"response": '{"x": 55, "y": 66}'},
            raise_for_status=lambda: None,
        )

        with patch.dict(os.environ, {}, clear=True):
            provider = OllamaVisionProvider()
            with patch("peekxd.vision.ollama._encode_image", return_value="base64img"):
                result = provider.find_element("/tmp/img.png", "a button")

        self.assertEqual(result, (55, 66))

    @patch("requests.post")
    def test_find_element_not_found(self, mock_post):
        """find_element returns None for negative coordinates."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"response": '{"x": -1, "y": -1}'},
            raise_for_status=lambda: None,
        )

        with patch.dict(os.environ, {}, clear=True):
            provider = OllamaVisionProvider()
            with patch("peekxd.vision.ollama._encode_image", return_value="base64img"):
                result = provider.find_element("/tmp/img.png", "nonexistent")

        self.assertIsNone(result)

    @patch("requests.post")
    def test_answer_question(self, mock_post):
        """answer_question delegates to analyze."""
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"response": "It is a dog."},
            raise_for_status=lambda: None,
        )

        with patch.dict(os.environ, {}, clear=True):
            provider = OllamaVisionProvider()
            with patch("peekxd.vision.ollama._encode_image", return_value="base64img"):
                result = provider.answer_question("/tmp/img.png", "Animal?")

        self.assertEqual(result, "It is a dog.")


class TestHermesVisionProvider(unittest.TestCase):
    """Test Hermes native vision provider."""

    def test_name(self):
        self.assertEqual(HermesVisionProvider().name, "hermes")

    @patch("peekxd.vision.hermes.HermesVisionProvider._hermes_agent_dir")
    def test_available_when_hermes_vision_tools_exist(self, mock_dir):
        mock_dir.return_value = Path("/tmp/hermes-agent")
        with patch("pathlib.Path.is_file", return_value=True):
            self.assertTrue(HermesVisionProvider().available)

    @patch("peekxd.vision.hermes.HermesVisionProvider._call_hermes", return_value="Hermes says hello")
    def test_analyze_uses_hermes_vision_tool(self, mock_call):
        provider = HermesVisionProvider()
        result = provider.analyze("/tmp/img.png", "Describe this")
        self.assertEqual(result, "Hermes says hello")
        mock_call.assert_called_once_with("/tmp/img.png", "Describe this")

    @patch("peekxd.vision.hermes.HermesVisionProvider._call_hermes", return_value='```json\n{"x": 7, "y": 9}\n```')
    def test_find_element_parses_coordinates(self, mock_call):
        provider = HermesVisionProvider()
        self.assertEqual(provider.find_element("/tmp/img.png", "the button"), (7, 9))

    @patch("peekxd.vision.hermes.HermesVisionProvider._call_hermes", return_value='{"x": -1, "y": -1}')
    def test_find_element_not_found(self, mock_call):
        provider = HermesVisionProvider()
        self.assertIsNone(provider.find_element("/tmp/img.png", "missing"))

    @patch("peekxd.vision.hermes.HermesVisionProvider._call_hermes", return_value="42")
    def test_answer_question_delegates_to_analyze(self, mock_call):
        provider = HermesVisionProvider()
        self.assertEqual(provider.answer_question("/tmp/img.png", "Answer?"), "42")


class TestGetVisionProvider(unittest.TestCase):
    """Test the provider detector."""

    @patch("peekxd.vision.detector.HermesVisionProvider")
    @patch("peekxd.vision.detector.OpenAIVisionProvider")
    @patch("peekxd.vision.detector.AnthropicVisionProvider")
    @patch("peekxd.vision.detector.OllamaVisionProvider")
    def test_specific_provider_available(self, mock_ollama, mock_anthropic, mock_openai, mock_hermes):
        """When a specific provider name is given and available, return it."""
        mock_instance = MagicMock()
        mock_instance.available = True
        mock_openai.return_value = mock_instance
        mock_hermes.return_value = MagicMock(available=False)
        mock_anthropic.return_value = MagicMock(available=False)
        mock_ollama.return_value = MagicMock(available=False)

        result = get_vision_provider("openai")
        self.assertEqual(result, mock_instance)

    @patch("peekxd.vision.detector.HermesVisionProvider")
    @patch("peekxd.vision.detector.OpenAIVisionProvider")
    @patch("peekxd.vision.detector.AnthropicVisionProvider")
    @patch("peekxd.vision.detector.OllamaVisionProvider")
    def test_specific_provider_unavailable(self, mock_ollama, mock_anthropic, mock_openai, mock_hermes):
        """When a specific provider name is unavailable, raise."""
        mock_instance = MagicMock()
        mock_instance.available = False
        mock_openai.return_value = mock_instance
        mock_hermes.return_value = MagicMock(available=False)
        mock_anthropic.return_value = MagicMock(available=False)
        mock_ollama.return_value = MagicMock(available=False)

        with self.assertRaises(ProviderNotAvailableError) as ctx:
            get_vision_provider("openai")
        self.assertIn("not available", str(ctx.exception))

    @patch("peekxd.vision.detector.HermesVisionProvider")
    @patch("peekxd.vision.detector.OpenAIVisionProvider")
    @patch("peekxd.vision.detector.AnthropicVisionProvider")
    @patch("peekxd.vision.detector.OllamaVisionProvider")
    def test_auto_select_prefers_hermes(self, mock_ollama, mock_anthropic, mock_openai, mock_hermes):
        """Auto-select prefers Hermes when available."""
        mock_hermes_instance = MagicMock()
        mock_hermes_instance.available = True
        mock_hermes.return_value = mock_hermes_instance
        mock_openai.return_value = MagicMock(available=True)
        mock_anthropic.return_value = MagicMock(available=True)
        mock_ollama.return_value = MagicMock(available=True)

        result = get_vision_provider()
        self.assertEqual(result, mock_hermes_instance)

    @patch("peekxd.vision.detector.HermesVisionProvider")
    @patch("peekxd.vision.detector.OpenAIVisionProvider")
    @patch("peekxd.vision.detector.AnthropicVisionProvider")
    @patch("peekxd.vision.detector.OllamaVisionProvider")
    def test_auto_select_falls_back_after_hermes(self, mock_ollama, mock_anthropic, mock_openai, mock_hermes):
        """Auto-select falls back to existing providers if Hermes is unavailable."""
        mock_hermes.return_value = MagicMock(available=False)
        mock_openai_instance = MagicMock()
        mock_openai_instance.available = False
        mock_openai.return_value = mock_openai_instance
        mock_anthropic_instance = MagicMock()
        mock_anthropic_instance.available = True
        mock_anthropic.return_value = mock_anthropic_instance
        mock_ollama.return_value = MagicMock(available=False)

        result = get_vision_provider()
        self.assertEqual(result, mock_anthropic_instance)

    @patch("peekxd.vision.detector.HermesVisionProvider")
    @patch("peekxd.vision.detector.OpenAIVisionProvider")
    @patch("peekxd.vision.detector.AnthropicVisionProvider")
    @patch("peekxd.vision.detector.OllamaVisionProvider")
    @patch("peekxd.vision.detector.OpenAICompatVisionProvider")
    def test_no_providers_available(self, mock_openai_compat, mock_ollama, mock_anthropic, mock_openai, mock_hermes):
        """When no provider is available, raise ProviderNotAvailableError."""
        mock_hermes.return_value = MagicMock(available=False)
        mock_openai.return_value = MagicMock(available=False)
        mock_anthropic.return_value = MagicMock(available=False)
        mock_ollama.return_value = MagicMock(available=False)
        mock_openai_compat.return_value = MagicMock(available=False)

        with self.assertRaises(ProviderNotAvailableError) as ctx:
            get_vision_provider()
        self.assertIn("No vision provider available", str(ctx.exception))

    @patch("peekxd.vision.detector.HermesVisionProvider")
    @patch("peekxd.vision.detector.OpenAIVisionProvider")
    @patch("peekxd.vision.detector.AnthropicVisionProvider")
    @patch("peekxd.vision.detector.OllamaVisionProvider")
    def test_unknown_provider_name(self, mock_ollama, mock_anthropic, mock_openai, mock_hermes):
        """An unknown provider name falls through to auto-selection."""
        mock_hermes.return_value = MagicMock(available=False)
        mock_openai.return_value = MagicMock(available=False)
        mock_anthropic.return_value = MagicMock(available=False)
        mock_ollama.return_value = MagicMock(available=True)

        result = get_vision_provider("unknown")
        self.assertEqual(result, mock_ollama.return_value)


class TestImports(unittest.TestCase):
    """Test that all public symbols are importable from the package."""

    def test_vision_imports(self):
        from peekxd.vision import (
            VisionProvider,
            OpenAIVisionProvider,
            AnthropicVisionProvider,
            OllamaVisionProvider,
            HermesVisionProvider,
            get_vision_provider,
        )
        self.assertTrue(issubclass(VisionProvider, ABC))
        self.assertTrue(callable(HermesVisionProvider))
        self.assertTrue(callable(get_vision_provider))


if __name__ == "__main__":
    unittest.main()
