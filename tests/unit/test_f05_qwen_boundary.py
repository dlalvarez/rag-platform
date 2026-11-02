import pytest

from rag_platform.embeddings.contracts import EmbeddingError
from rag_platform.embeddings.qwen import LocalQwen, qwen_profile, verify_artifacts


class CountingTokenizer:
    def encode(self, text, **kwargs):
        return list(range(513))


class ModelMustNotRun:
    def __call__(self, *args, **kwargs):
        raise AssertionError("over-limit input reached inference")


def test_qwen_refuses_missing_artifacts_before_optional_import(tmp_path):
    with pytest.raises(EmbeddingError, match="DEPENDENCY_UNAVAILABLE"):
        LocalQwen.load(tmp_path)


def test_qwen_refuses_symlink_model_root(tmp_path):
    root = tmp_path / "link"
    root.symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(EmbeddingError, match="DEPENDENCY_UNAVAILABLE"):
        verify_artifacts(root)


def test_qwen_does_not_infer_or_truncate_over_limit_input():
    provider = LocalQwen(CountingTokenizer(), ModelMustNotRun(), None)
    with pytest.raises(EmbeddingError, match="INPUT_TOO_LONG"):
        provider.embed(["private content"], "passage")
    assert "private content" not in repr(provider)


def test_qwen_limit_failure_releases_inference_capacity():
    provider = LocalQwen(CountingTokenizer(), ModelMustNotRun(), None)
    for _ in range(2):
        with pytest.raises(EmbeddingError, match="INPUT_TOO_LONG"):
            provider.embed(["private content"], "query")


def test_qwen_profile_cannot_be_changed_by_caller():
    from dataclasses import FrozenInstanceError

    profile = qwen_profile()
    with pytest.raises(FrozenInstanceError):
        profile.dimension = 384
    assert profile.dimension == 1024


def test_qwen_profile_includes_instruction_and_operational_limit():
    profile = qwen_profile()
    assert profile.query_prefix.endswith("\nQuery:")
    assert profile.passage_prefix == ""
    assert profile.max_tokens == 512
    assert profile.max_batch == 4


def test_qwen_refuses_arbitrary_path_type():
    with pytest.raises(EmbeddingError, match="DEPENDENCY_UNAVAILABLE"):
        verify_artifacts("https://example.invalid/model")


def test_qwen_rejects_concurrent_inference_instead_of_queueing_private_inputs():
    from rag_platform.embeddings.qwen import _INFERENCE

    provider = LocalQwen(CountingTokenizer(), ModelMustNotRun(), None)
    assert _INFERENCE.acquire(blocking=False)
    try:
        with pytest.raises(EmbeddingError, match="LIMIT_EXCEEDED"):
            provider.embed(["private input"], "query")
    finally:
        _INFERENCE.release()


def test_qwen_dependency_error_contains_no_private_input():
    class BrokenTokenizer:
        def encode(self, text, **kwargs):
            raise RuntimeError(text)

    provider = LocalQwen(BrokenTokenizer(), ModelMustNotRun(), None)
    with pytest.raises(EmbeddingError) as error:
        provider.embed(["sensitive document"], "passage")
    assert str(error.value) == "DEPENDENCY_UNAVAILABLE"
    assert error.value.__suppress_context__
