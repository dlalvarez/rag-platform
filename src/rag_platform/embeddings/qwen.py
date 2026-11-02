"""Pinned local CPU Qwen adapter. Optional dependencies; no network or storage writes."""

import hashlib
import threading
from dataclasses import dataclass, field
from pathlib import Path

from rag_platform.embeddings.contracts import (
    EmbeddingBatch,
    EmbeddingError,
    EmbeddingProfile,
    inputs,
    validate,
)

REVISION = "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"
QUERY_PREFIX = (
    "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery:"
)
_INFERENCE = threading.BoundedSemaphore(1)


def qwen_profile():
    return EmbeddingProfile(
        provider="local-qwen-cpu",
        model="Qwen/Qwen3-Embedding-0.6B",
        model_revision=REVISION,
        tokenizer="Qwen/Qwen3-Embedding-0.6B",
        tokenizer_revision=REVISION,
        dimension=1024,
        metric="cosine",
        max_tokens=512,
        normalization="l2",
        query_prefix=QUERY_PREFIX,
        passage_prefix="",
        adapter_revision="qwen-last-token-eos-f32-v1",
        max_batch=4,
    )


def verify_artifacts(root):
    """Compare operator-installed public files with pinned upstream identities."""
    if not isinstance(root, Path) or root.is_symlink() or not root.is_dir():
        raise EmbeddingError("DEPENDENCY_UNAVAILABLE")
    for name, size, expected, algorithm in ARTIFACTS:
        path = root / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
            raise EmbeddingError("DEPENDENCY_UNAVAILABLE")
        digest = hashlib.new(algorithm)
        if algorithm == "sha1":
            digest.update(b"blob " + str(size).encode() + b"\0")
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise EmbeddingError("DEPENDENCY_UNAVAILABLE")


@dataclass(frozen=True, slots=True, repr=False)
class LocalQwen:
    _tokenizer: object = field(repr=False)
    _model: object = field(repr=False)
    _torch: object = field(repr=False)
    profile: EmbeddingProfile = field(default_factory=qwen_profile, init=False)

    @classmethod
    def load(cls, root):
        if not _INFERENCE.acquire(blocking=False):
            raise EmbeddingError("LIMIT_EXCEEDED")
        try:
            verify_artifacts(root)
            from importlib.metadata import version

            import torch
            from transformers import AutoModel, AutoTokenizer

            for package, expected in (
                ("torch", "2.7.1+cpu"),
                ("transformers", "4.51.3"),
                ("tokenizers", "0.21.4"),
                ("safetensors", "0.5.3"),
            ):
                if version(package) != expected:
                    raise EmbeddingError("DEPENDENCY_UNAVAILABLE")
            torch.set_num_threads(2)
            tokenizer = AutoTokenizer.from_pretrained(
                str(root), local_files_only=True, trust_remote_code=False, padding_side="left"
            )
            model = (
                AutoModel.from_pretrained(
                    str(root),
                    local_files_only=True,
                    trust_remote_code=False,
                    use_safetensors=True,
                    torch_dtype=torch.float32,
                    attn_implementation="sdpa",
                )
                .to("cpu")
                .eval()
            )
            model.config.use_cache = False
            if model.config.hidden_size != 1024:
                raise EmbeddingError("PROFILE_MISMATCH")
            return cls(tokenizer, model, torch)
        except EmbeddingError:
            raise
        except Exception:
            raise EmbeddingError("DEPENDENCY_UNAVAILABLE") from None
        finally:
            _INFERENCE.release()

    def count_tokens(self, text, kind):
        inputs(self.profile, [text], kind)
        prefix = self.profile.query_prefix if kind == "query" else self.profile.passage_prefix
        try:
            return len(
                self._tokenizer.encode(prefix + text, add_special_tokens=True, truncation=False)
            )
        except Exception:
            raise EmbeddingError("DEPENDENCY_UNAVAILABLE") from None

    def embed(self, texts, kind):
        inputs(self.profile, texts, kind)
        if not _INFERENCE.acquire(blocking=False):
            raise EmbeddingError("LIMIT_EXCEEDED")
        try:
            counts = tuple(self.count_tokens(text, kind) for text in texts)
            if any(n > self.profile.max_tokens for n in counts):
                raise EmbeddingError("INPUT_TOO_LONG")
            prefix = self.profile.query_prefix if kind == "query" else self.profile.passage_prefix
            encoded = self._tokenizer(
                [prefix + text for text in texts],
                padding=True,
                truncation=False,
                add_special_tokens=True,
                return_tensors="pt",
            )
            if tuple(encoded["attention_mask"].sum(dim=1).tolist()) != counts:
                raise EmbeddingError("INPUT_INVALID")
            with self._torch.inference_mode():
                hidden = self._model(**encoded, use_cache=False).last_hidden_state
                # Left padding means the final non-padding/EOS token is at -1.
                if not bool(encoded["attention_mask"][:, -1].all()):
                    raise EmbeddingError("INPUT_INVALID")
                vectors = self._torch.nn.functional.normalize(hidden[:, -1, :].float(), p=2, dim=1)
                result = tuple(tuple(row) for row in vectors.tolist())
            return validate(
                self.profile,
                texts,
                kind,
                EmbeddingBatch(self.profile.fingerprint(), result, counts),
            )
        except EmbeddingError:
            raise
        except Exception:
            raise EmbeddingError("DEPENDENCY_UNAVAILABLE") from None
        finally:
            _INFERENCE.release()

    def __repr__(self):
        return "LocalQwen(<pinned public model; private inputs>)"


ARTIFACTS = (
    ("1_Pooling/config.json", 313, "b6291baabbc39f9792d6759883a47d7d5bd0fbcf", "sha1"),
    ("README.md", 17237, "00a82ea60dfb1d8aed899c16e2b4f12673cd2f79", "sha1"),
    ("config.json", 727, "cef2749ee93607b8f9a58ec72f4f6bfaf874e71d", "sha1"),
    ("config_sentence_transformers.json", 215, "76aef3ade63553ebb698fe3c2a3264040ed093f8", "sha1"),
    ("merges.txt", 1671853, "31349551d90c7606f325fe0f11bbb8bd5fa0d7c7", "sha1"),
    (
        "model.safetensors",
        1191586416,
        "0437e45c94563b09e13cb7a64478fc406947a93cb34a7e05870fc8dcd48e23fd",
        "sha256",
    ),
    ("modules.json", 349, "952a9b81c0bfd99800fabf352f69c7ccd46c5e43", "sha1"),
    (
        "tokenizer.json",
        11423705,
        "def76fb086971c7867b829c23a26261e38d9d74e02139253b38aeb9df8b4b50a",
        "sha256",
    ),
    ("tokenizer_config.json", 9706, "7345216a0785dc7086e8c245b2a9d3896ce2b756", "sha1"),
    ("vocab.json", 2776833, "4783fe10ac3adce15ac8f358ef5462739852c569", "sha1"),
)
