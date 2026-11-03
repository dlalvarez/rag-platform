"""Explicit test fixture, no real semantic quality claim or runtime activation."""

from dataclasses import dataclass

from rag_platform.providers.generation import (
    STATUSES,
    GenerationError,
    GenerationProfile,
    GenerationReply,
    GenerationRequest,
    render,
    request_budget,
    text,
    validate,
)


def fixture_profile(**changes):
    values = dict(
        provider="fixture",
        model="offline-chat",
        revision="fixture-v1",
        runtime_revision="python-v1",
        artifact_sha256="0" * 64,
        tokenizer_revision="four-utf8-bytes-v1",
        template_revision="json-data-v1",
        max_context_tokens=2048,
        max_output_tokens=256,
        timeout_seconds=30,
    )
    return GenerationProfile(**(values | changes))


@dataclass(frozen=True, slots=True, repr=False)
class FixtureAnswer:
    status: str
    answer: str
    citations: tuple[str, ...] = ()

    def __post_init__(self):
        if (
            not isinstance(self.status, str)
            or self.status not in STATUSES
            or not text(self.answer, 8192)
            or type(self.citations) is not tuple
            or len(self.citations) > 8
            or any(not isinstance(value, str) for value in self.citations)
        ):
            raise GenerationError("INPUT_INVALID")

    def __repr__(self):
        return "FixtureAnswer(<synthetic test response>)"


class DeterministicChatFixture:
    def __init__(self, answers=None, *, profile=None):
        self.profile = fixture_profile() if profile is None else profile
        if not isinstance(self.profile, GenerationProfile) or self.profile.provider != "fixture":
            raise GenerationError("INPUT_INVALID")
        if answers is not None and (not isinstance(answers, dict) or len(answers) > 128):
            raise GenerationError("INPUT_INVALID")
        self.answers = dict(answers or {})
        if any(
            not isinstance(key, str) or not isinstance(value, FixtureAnswer)
            for key, value in self.answers.items()
        ):
            raise GenerationError("INPUT_INVALID")
        self.calls = 0

    def count_tokens(self, request):
        prompt = render(request)
        # Deterministic synthetic tokenizer of the fully rendered prompt, never a real model claim.
        return max(1, (len(prompt.system.encode()) + len(prompt.user.encode()) + 3) // 4)

    def generate(self, request):
        if not isinstance(request, GenerationRequest):
            raise GenerationError("INPUT_INVALID")
        count = self.count_tokens(request)
        request_budget(self.profile, request, count)
        self.calls += 1
        result = self.answers.get(
            request.question, FixtureAnswer("abstained", "Insufficient evidence.")
        )
        reply = GenerationReply(
            self.profile.fingerprint(),
            result.status,
            result.answer,
            result.citations,
            count,
            max(1, (len(result.answer.encode()) + 3) // 4),
        )
        return validate(self.profile, request, reply, count)

    def __repr__(self):
        return "DeterministicChatFixture(<offline synthetic provider>)"
