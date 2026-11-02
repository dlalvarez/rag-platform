"""Embedding contract gates independent of D06, offline with no network/model weights."""

from dataclasses import FrozenInstanceError, replace

import pytest

from rag_platform.embeddings.contracts import EmbeddingBatch, EmbeddingError, inputs, validate
from rag_platform.embeddings.fixture import DeterministicFixture, fixture_profile


def test_fixture_is_replayable_and_batch_order_preserved():
    provider = DeterministicFixture(fixture_profile())
    texts = ["SQL SELECT con Café", "second synthetic passage"]
    first = provider.embed(texts, "passage")
    assert provider.embed(texts, "passage") == first
    assert provider.embed(list(reversed(texts)), "passage").vectors == tuple(
        reversed(first.vectors)
    )
    assert first.total_tokens == sum(first.input_tokens)
    assert validate(provider.profile, texts, "passage", first) == first


@pytest.mark.parametrize(
    "change",
    [
        {"model": "other"},
        {"model_revision": "v2"},
        {"tokenizer_revision": "v2"},
        {"adapter_revision": "v2"},
        {"passage_prefix": "other: "},
        {"metric": "l2"},
        {"dimension": 5},
        {"max_tokens": 64},
    ],
)
def test_same_dimension_different_semantics_cannot_be_adopted(change):
    profile = fixture_profile()
    batch = DeterministicFixture(profile).embed(["synthetic"], "query")
    changed = replace(profile, **change)
    assert changed.fingerprint() != profile.fingerprint()
    with pytest.raises(EmbeddingError, match="PROFILE_MISMATCH"):
        validate(changed, ["synthetic"], "query", batch)


@pytest.mark.parametrize("value", [True, 0, -1, 2001, "384", None])
def test_invalid_dimension_rejected_before_inference(value):
    with pytest.raises(EmbeddingError, match="INPUT_INVALID"):
        fixture_profile(dimension=value)


@pytest.mark.parametrize(
    "vectors",
    [
        (),
        ((1.0, 0.0),),
        ((1.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
    ],
)
def test_wrong_dimension_or_count_fails_whole_batch(vectors):
    profile = fixture_profile()
    with pytest.raises(EmbeddingError, match="DIMENSION_MISMATCH"):
        validate(
            profile, ["fixture"], "passage", EmbeddingBatch(profile.fingerprint(), vectors, (3,))
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, "1", 10**500])
def test_nonfinite_nonreal_or_float32_overflow_never_validates(value):
    profile = fixture_profile()
    batch = EmbeddingBatch(profile.fingerprint(), ((value, 0.0, 0.0),), (3,))
    with pytest.raises(EmbeddingError, match="INVALID_VECTOR"):
        validate(profile, ["fixture"], "passage", batch)


@pytest.mark.parametrize("vector", [(0.0, 0.0, 0.0), (0.1, 0.2, 0.3)])
def test_cosine_zero_and_declared_l2_norm_violation_rejected(vector):
    profile = fixture_profile()
    with pytest.raises(EmbeddingError, match="INVALID_VECTOR"):
        validate(
            profile, ["fixture"], "query", EmbeddingBatch(profile.fingerprint(), (vector,), (3,))
        )


@pytest.mark.parametrize("texts", [[], (), "not a batch", [" "], [b"bytes"], ["x\0y"], ["\ud800"]])
def test_invalid_inputs_fail_without_echo(texts):
    with pytest.raises(EmbeddingError) as result:
        inputs(fixture_profile(), texts, "passage")
    assert str(result.value) in EmbeddingError.CODES


def test_token_budget_includes_fixture_prefix_and_special_tokens_without_truncation():
    provider = DeterministicFixture(fixture_profile(max_tokens=4))
    assert provider.embed(["one"], "query").input_tokens == (4,)
    with pytest.raises(EmbeddingError, match="INPUT_TOO_LONG"):
        provider.embed(["one two"], "query")


def test_batch_and_character_limits_reject_before_hashing():
    profile = fixture_profile(max_batch=1)
    with pytest.raises(EmbeddingError, match="LIMIT_EXCEEDED"):
        DeterministicFixture(profile).embed(["one", "two"], "query")
    with pytest.raises(EmbeddingError, match="LIMIT_EXCEEDED"):
        inputs(profile, ["x" * 8193], "passage")


@pytest.mark.parametrize("tokens", [(True,), (0,), (-1,), (), (9999,)])
def test_provider_token_metadata_is_bounded(tokens):
    profile = fixture_profile()
    with pytest.raises(EmbeddingError):
        validate(
            profile,
            ["fixture"],
            "passage",
            EmbeddingBatch(profile.fingerprint(), ((1.0, 0.0, 0.0),), tokens),
        )


def test_private_representations_and_errors_never_include_payload():
    provider = DeterministicFixture(fixture_profile())
    batch = provider.embed(["PRIVATE_EMBEDDING_CANARY"], "passage")
    assert "PRIVATE_EMBEDDING_CANARY" not in repr(batch)
    assert str(batch.vectors[0][0]) not in repr(batch)
    assert "PRIVATE_EMBEDDING_CANARY" not in str(EmbeddingError("PRIVATE_EMBEDDING_CANARY"))
    assert "not a semantic model" in repr(provider)
    with pytest.raises(FrozenInstanceError):
        provider.profile.dimension = 384


def test_fixture_cannot_impersonate_a_real_provider():
    with pytest.raises(EmbeddingError, match="PROFILE_MISMATCH"):
        DeterministicFixture(replace(fixture_profile(), provider="local"))


def test_profile_fingerprint_is_canonical_not_field_construction_order():
    profile = fixture_profile()
    assert replace(profile).fingerprint() == profile.fingerprint()


def test_fixture_profile_cannot_be_swapped_after_validation():
    provider = DeterministicFixture(fixture_profile())
    with pytest.raises(FrozenInstanceError):
        provider.profile = replace(provider.profile, provider="local")


def test_missing_profile_is_a_closed_input_error():
    with pytest.raises(EmbeddingError, match="INPUT_INVALID"):
        inputs(None, ["synthetic"], "query")


def test_profile_supports_fixed_multiline_query_instruction():
    from dataclasses import replace

    from rag_platform.embeddings.fixture import fixture_profile

    profile = replace(
        fixture_profile(), query_prefix="Instruct: Retrieve relevant passages\nQuery:"
    )
    assert profile.fingerprint() != fixture_profile().fingerprint()


def test_profile_rejects_carriage_return_in_instruction():
    from dataclasses import replace

    import pytest

    from rag_platform.embeddings.contracts import EmbeddingError
    from rag_platform.embeddings.fixture import fixture_profile

    with pytest.raises(EmbeddingError, match="INPUT_INVALID"):
        replace(fixture_profile(), query_prefix="query:\r")
