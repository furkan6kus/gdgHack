from pathlib import Path

import pytest

from mytool.core.config import DENY_PATTERNS, has_api_key, is_denied, load_config


def test_defaults() -> None:
    config = load_config({})
    assert config.model == "claude-sonnet-5-5"
    assert config.max_tokens_per_request == 16000
    assert config.effort == "medium"
    assert config.max_findings == 20
    assert config.subprocess_timeout_s == 60
    assert config.verify is True


def test_env_model() -> None:
    assert load_config({"MYTOOL_MODEL": "m1"}).model == "m1"


def test_overrides_beat_env() -> None:
    config = load_config({"MYTOOL_MODEL": "m1"}, model="m2", max_findings=5)
    assert (config.model, config.max_findings) == ("m2", 5)


def test_none_overrides_ignored() -> None:
    config = load_config({"MYTOOL_MODEL": "m1"}, model=None, max_findings=None)
    assert (config.model, config.max_findings) == ("m1", 20)


def test_has_api_key() -> None:
    assert not has_api_key({})
    assert not has_api_key({"ANTHROPIC_API_KEY": ""})
    assert has_api_key({"ANTHROPIC_API_KEY": "sk-x"})


def test_config_does_not_store_key() -> None:
    assert "sk-x" not in load_config({"ANTHROPIC_API_KEY": "sk-x"}).model_dump_json()


@pytest.mark.parametrize(
    "name",
    [".env", ".env.local", "a.pem", "A.KEY", "id_rsa", "id_rsa.pub", "my_Secret.txt",
     "credentials.json", "x.p12"],
)  # fmt: skip
def test_denied(name: str) -> None:
    assert is_denied(Path("dir") / name, DENY_PATTERNS)


@pytest.mark.parametrize("name", ["main.py", "environment.py", "keyboard.py"])
def test_not_denied(name: str) -> None:
    assert not is_denied(Path(name), DENY_PATTERNS)
