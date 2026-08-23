"""
mockllm: a fake model client with a real client's shape.

Every exercise in this course runs against this instead of a live model. You get
the same objects an SDK would hand you, so the loop you write here is the loop
you would write against a real provider. What you do not get is a network call,
an API key, a bill, or a different answer every time you press run.

The response shape follows the OpenAI chat completions API, which most providers
now mirror.

    from mockllm import MockClient, text, tool_call

    client = MockClient([
        tool_call("calculator", {"expression": "(19 * 42) - 8"}),
        text("The answer is 790."),
    ])

    response = client.chat.completions.create(
        model="mock",
        messages=[{"role": "user", "content": "What is (19 * 42) - 8?"}],
        tools=TOOLS,
    )

    response.choices[0].finish_reason        # "tool_calls"
    response.choices[0].message.tool_calls   # [ToolCall(...)]

Each call to create() consumes the next scripted response. Running past the end
of the script raises ScriptExhausted, which almost always means your loop failed
to terminate.

This module has no dependencies outside the standard library.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any, Iterable


class MockLLMError(Exception):
    """Base class for every error this module raises."""


class ScriptExhausted(MockLLMError):
    """
    The loop asked for more responses than the script provides.

    In an agent loop this nearly always means the loop did not stop when the
    model stopped asking for tools. Check that you break out on a finish_reason
    of "stop", and that max_iter is doing its job.
    """


class APIError(MockLLMError):
    """
    A simulated provider failure, for exercises about error handling.

    Scripted with error(): the client raises this instead of returning.
    """

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class Function:
    name: str
    arguments: str  # JSON, exactly as a real provider sends it

    def parsed_arguments(self) -> dict[str, Any]:
        """Convenience for tests. Real SDKs make you call json.loads yourself."""
        return json.loads(self.arguments)


@dataclass(frozen=True)
class ToolCall:
    id: str
    function: Function
    type: str = "function"


@dataclass(frozen=True)
class Message:
    role: str = "assistant"
    content: str | None = None
    tool_calls: list[ToolCall] | None = None


@dataclass(frozen=True)
class Choice:
    message: Message
    finish_reason: str
    index: int = 0


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass(frozen=True)
class Completion:
    choices: list[Choice]
    usage: Usage
    model: str = "mock"


# Script builders. Each returns an opaque step that MockClient knows how to play.


@dataclass(frozen=True)
class _TextStep:
    content: str
    finish_reason: str = "stop"


@dataclass(frozen=True)
class _ToolStep:
    calls: list[tuple[str, dict[str, Any]]]


@dataclass(frozen=True)
class _ErrorStep:
    message: str
    status_code: int


Step = _TextStep | _ToolStep | _ErrorStep


def text(content: str) -> Step:
    """A plain assistant reply. finish_reason will be "stop"."""
    return _TextStep(content)


def truncated(content: str) -> Step:
    """
    A reply that ran out of output budget mid sentence.

    finish_reason will be "length". Code that treats this as a finished answer
    is the bug this step exists to catch.
    """
    return _TextStep(content, finish_reason="length")


def tool_call(name: str, arguments: dict[str, Any]) -> Step:
    """A single tool call. finish_reason will be "tool_calls"."""
    return _ToolStep([(name, arguments)])


def tool_calls(calls: Iterable[tuple[str, dict[str, Any]]]) -> Step:
    """
    Several tool calls in one turn, which real models do when the calls are
    independent of each other.
    """
    calls = list(calls)
    if not calls:
        raise ValueError("tool_calls() needs at least one call")
    return _ToolStep(calls)


def error(message: str = "service unavailable", status_code: int = 503) -> Step:
    """Make the next create() raise APIError instead of returning."""
    return _ErrorStep(message, status_code)


@dataclass
class _Completions:
    _client: MockClient

    def create(
        self,
        *,
        model: str = "mock",
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> Completion:
        return self._client._next(model=model, messages=messages, tools=tools, **kwargs)


@dataclass
class _Chat:
    completions: _Completions


# Embeddings.
#
# These are real vectors, not random ones, so cosine similarity between them
# means something and retrieval exercises actually retrieve. The catch is that
# they measure word overlap and nothing more. "car" and "automobile" score zero
# against each other here, where a trained embedding model would put them close
# together. Everything you build against this works the same way with a real
# embedding API; it just gets better at synonyms.

EMBEDDING_DIMENSIONS = 256

_WORD = re.compile(r"[a-z0-9']+")


def _hash_dimension(token: str) -> int:
    """A stable hash. Python's built in hash() is salted per process."""
    digest = 2166136261
    for byte in token.encode("utf8"):
        digest = ((digest ^ byte) * 16777619) & 0xFFFFFFFF
    return digest % EMBEDDING_DIMENSIONS


def embed_text(content: str) -> list[float]:
    """
    Turn text into a unit length vector by hashing its words into buckets.

    Known as the hashing trick. It is what you would reach for before embedding
    models existed, and it is enough to make retrieval behave sensibly.
    """
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in _WORD.findall(content.lower()):
        vector[_hash_dimension(token)] += 1.0

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


@dataclass(frozen=True)
class Embedding:
    embedding: list[float]
    index: int


@dataclass(frozen=True)
class EmbeddingResponse:
    data: list[Embedding]
    model: str = "mock-embed"


@dataclass
class _Embeddings:
    _client: MockClient

    def create(
        self, *, input: str | list[str], model: str = "mock-embed", **kwargs: Any
    ) -> EmbeddingResponse:
        del kwargs
        texts = [input] if isinstance(input, str) else list(input)
        self._client.embedding_requests.append(texts)
        return EmbeddingResponse(
            data=[Embedding(embedding=embed_text(t), index=i) for i, t in enumerate(texts)],
            model=model,
        )


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    How aligned two vectors are, from -1 to 1.

    Both vectors from embed_text() are already unit length, so this reduces to a
    dot product. The division is kept so the function stays correct if you hand
    it vectors from somewhere else.
    """
    if len(a) != len(b):
        raise ValueError(f"vectors have different lengths: {len(a)} and {len(b)}")
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


@dataclass
class MockClient:
    """
    A scripted stand-in for a provider client.

    Args:
        script: the responses to return, in order, built with text(),
            tool_call(), tool_calls() and error().
        strict: when True (the default), running past the end of the script
            raises ScriptExhausted. Set False to repeat the final step forever,
            which is occasionally useful while exploring.
    """

    #: Empty is allowed when you only need embeddings. Calling create() on an
    #: empty script raises ScriptExhausted.
    script: list[Step] = field(default_factory=list)
    strict: bool = True

    #: Every kwargs dict passed to create(), in order. Tests assert against this
    #: to check what the loop actually sent, not just what it got back.
    requests: list[dict[str, Any]] = field(default_factory=list)

    #: Every batch of texts passed to embeddings.create(), in order.
    embedding_requests: list[list[str]] = field(default_factory=list)

    _cursor: int = field(default=0, init=False, repr=False)
    chat: _Chat = field(init=False, repr=False)
    embeddings: _Embeddings = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.chat = _Chat(completions=_Completions(self))
        self.embeddings = _Embeddings(self)

    @property
    def call_count(self) -> int:
        return len(self.requests)

    def _next(self, **request: Any) -> Completion:
        # Snapshot rather than store a reference. A real client serializes the
        # request to JSON on the way out, so later mutations of the caller's
        # list cannot change what was sent. Recording the live list instead
        # would make `requests` show the final state of the conversation on
        # every entry, which quietly breaks any test asserting on what a
        # particular turn actually sent.
        self.requests.append(_snapshot(request))

        if self._cursor >= len(self.script):
            if not self.script:
                raise ScriptExhausted(
                    "This MockClient was built with no script, so it can only serve "
                    "embeddings. Pass responses to MockClient([...]) to use chat."
                )
            if self.strict:
                raise ScriptExhausted(
                    f"The script had {len(self.script)} response(s) but the loop asked "
                    f"for {self._cursor + 1}. An agent loop that runs past its script "
                    f"usually is not checking finish_reason, or has lost its max_iter guard."
                )
            step = self.script[-1]
        else:
            step = self.script[self._cursor]
            self._cursor += 1

        if isinstance(step, _ErrorStep):
            raise APIError(step.message, step.status_code)

        prompt_tokens = _estimate_tokens(request.get("messages") or [])

        if isinstance(step, _TextStep):
            return Completion(
                choices=[
                    Choice(
                        message=Message(content=step.content),
                        finish_reason=step.finish_reason,
                    )
                ],
                usage=Usage(prompt_tokens, _estimate_tokens([{"content": step.content}])),
            )

        calls = [
            ToolCall(
                id=f"call_{self._cursor}_{index}",
                function=Function(name=name, arguments=json.dumps(arguments)),
            )
            for index, (name, arguments) in enumerate(step.calls)
        ]
        return Completion(
            choices=[
                Choice(
                    message=Message(content=None, tool_calls=calls),
                    finish_reason="tool_calls",
                )
            ],
            usage=Usage(prompt_tokens, 12 * len(calls)),
        )


def _snapshot(value: Any) -> Any:
    """Deep copy the parts of a request that callers are likely to mutate."""
    if isinstance(value, dict):
        return {key: _snapshot(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_snapshot(item) for item in value]
    return value


def _estimate_tokens(messages: list[dict[str, Any]]) -> int:
    """
    A rough word based estimate, not a real tokenizer.

    It exists so usage numbers move in the right direction as a conversation
    grows, which is the thing worth noticing. Do not read anything into the
    exact value.
    """
    words = 0
    for message in messages:
        content = message.get("content")
        if isinstance(content, str):
            words += len(content.split())
    return max(1, int(words * 1.3))


__all__ = [
    "APIError",
    "Choice",
    "Completion",
    "EMBEDDING_DIMENSIONS",
    "Embedding",
    "EmbeddingResponse",
    "Function",
    "Message",
    "MockClient",
    "MockLLMError",
    "ScriptExhausted",
    "ToolCall",
    "Usage",
    "cosine_similarity",
    "embed_text",
    "error",
    "text",
    "tool_call",
    "tool_calls",
    "truncated",
]
