from types import SimpleNamespace
from typing import Any

import httpx2 as httpx
import pytest
from anthropic import (
    APIConnectionError,
    AuthenticationError,
    InternalServerError,
    NotFoundError,
    RateLimitError,
)

from mytool.core.config import Config
from mytool.core.llm import (
    AnthropicLLM,
    LLMError,
    LLMFindingRef,
    LLMFix,
    LLMRequest,
    LLMUnitResponse,
    number_lines,
    render_request,
)
from mytool.core.models import Category

REQ = LLMRequest(
    file_name="a.py",
    language="python",
    unit_name=None,
    start_line=1,
    code="1 | import os",
    findings=[LLMFindingRef("f1", "F401", 1, "unused")],
)
GOOD = LLMUnitResponse(
    fixes=[
        LLMFix(
            finding_ids=["f1"],
            category=Category.STYLE,
            explanation="e",
            original="import os\n",
            replacement="",
        )
    ]
)


def _response(parsed: object, stop: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        parsed_output=parsed,
        stop_reason=stop,
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )


class FakeClient:
    def __init__(self, *results: object) -> None:
        self.results = list(results)
        self.calls: list[dict[str, Any]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(parse=self._parse))

    def _parse(self, **kwargs: Any) -> object:
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def _llm(*results: object) -> tuple[AnthropicLLM, FakeClient]:
    client = FakeClient(*results)
    return AnthropicLLM(Config(), client), client


def _sdk_error(cls: type[Exception], status: int) -> Exception:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status, request=request)
    return cls("x", response=response, body=None)  # type: ignore[call-arg]


def test_success_returns_parsed_and_usage() -> None:
    llm, client = _llm(_response(GOOD))
    parsed, usage = llm.suggest(REQ)
    assert parsed == GOOD
    assert (usage.input_tokens, usage.output_tokens) == (10, 5)
    call = client.calls[0]
    assert call["model"] == "claude-sonnet-5-5"
    assert call["output_config"] == {"effort": "medium"}
    assert call["output_format"] is LLMUnitResponse
    for banned in ("temperature", "top_p", "top_k", "thinking"):
        assert banned not in call


def test_retry_once_on_none_then_success() -> None:
    llm, client = _llm(_response(None), _response(GOOD))
    parsed, usage = llm.suggest(REQ)
    assert parsed == GOOD
    assert len(client.calls) == 2
    assert usage.input_tokens == 20


def test_retry_on_validation_error() -> None:
    with pytest.raises(Exception) as info:
        LLMUnitResponse.model_validate({"fixes": "x"})
    llm, client = _llm(info.value, _response(GOOD))
    assert llm.suggest(REQ)[0] == GOOD
    assert len(client.calls) == 2


def test_two_failures_raise() -> None:
    llm, client = _llm(_response(None), _response(None))
    with pytest.raises(LLMError, match="geçersiz JSON"):
        llm.suggest(REQ)
    assert len(client.calls) == 2


def test_refusal() -> None:
    llm, _ = _llm(_response(None, "refusal"))
    with pytest.raises(LLMError, match="reddetti"):
        llm.suggest(REQ)


def test_max_tokens() -> None:
    llm, _ = _llm(_response(None, "max_tokens"))
    with pytest.raises(LLMError, match="--max-tokens"):
        llm.suggest(REQ)


@pytest.mark.parametrize(
    ("error", "text", "fatal"),
    [
        (_sdk_error(AuthenticationError, 401), "API anahtarı geçersiz", True),
        (_sdk_error(NotFoundError, 404), "--model", True),
        (_sdk_error(RateLimitError, 429), "hız sınırı", True),
        (
            APIConnectionError(request=httpx.Request("POST", "https://x")),
            "ağ hatası",
            True,
        ),
        (_sdk_error(InternalServerError, 500), "API hatası 500", False),
    ],
)
def test_error_mapping(error: Exception, text: str, fatal: bool) -> None:
    llm, _ = _llm(error)
    with pytest.raises(LLMError, match=text) as info:
        llm.suggest(REQ)
    assert info.value.fatal is fatal


def test_prompt_rendering() -> None:
    assert number_lines("a\nb", 9) == " 9 | a\n10 | b"
    text = render_request(REQ)
    assert "a.py" in text
    assert "id=f1" in text
