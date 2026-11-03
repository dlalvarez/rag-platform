"""Deterministic bounded corpus, durable checkpoints and exact INGEST scope, offline."""

import json
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import f05_multibatch_corpus as check  # noqa: E402

CORPUS = Path(__file__).resolve().parents[1] / "fixtures/f05/retrieval-es-en.json"


def fixture_scope():
    scope = [
        dict(name=name, tenant=str(uuid4())) for name in ("same-a", "same-b", "two-a", "two-b")
    ]
    manifest = dict(
        actors={"alice": str(uuid4())},
        fixtures=[
            dict(
                **r,
                repository=str(uuid4()),
                documents=[
                    dict(
                        case="positive-txt",
                        actor="alice",
                        document=str(uuid4()),
                        original=str(uuid4()),
                        mime="text/plain",
                        sha256=check.BODY_SHA,
                        byte_size=check.BODY_BYTES,
                    )
                ],
            )
            for r in scope
        ],
    )
    return scope, manifest


def test_public_corpus_is_deterministic_and_really_multibatch():
    first, count = check.body(CORPUS)
    second, repeated_count = check.body(CORPUS)
    assert first == second and count == repeated_count
    assert count == 14 and len(first) == check.BODY_BYTES
    assert first.decode("utf-8").startswith("F05_MULTIBATCH_PUBLIC_FIXTURE")


def test_changed_gold_does_not_create_a_corpus(tmp_path):
    changed = tmp_path / "changed.json"
    changed.write_bytes(CORPUS.read_bytes() + b" ")
    with pytest.raises(ValueError):
        check.body(changed)


def test_checkpoint_replay_preserves_inode_and_conflict_refuses(tmp_path, monkeypatch):
    monkeypatch.setattr(check, "OUT", tmp_path)
    value = {"id": str(uuid4()), "corpus_sha256": "a" * 64}
    check.save("run.json", value)
    inode = (tmp_path / "run.json").stat().st_ino
    check.save("run.json", value)
    assert json.loads((tmp_path / "run.json").read_text()) == value
    assert (tmp_path / "run.json").stat().st_ino == inode
    with pytest.raises(RuntimeError, match="CHECKPOINT_CONFLICT"):
        check.save("run.json", {**value, "id": str(uuid4())})


def test_checkpoint_symlink_is_never_followed(tmp_path, monkeypatch):
    monkeypatch.setattr(check, "OUT", tmp_path)
    target = tmp_path / "preserved.json"
    target.write_text("preserve")
    (tmp_path / "run.json").symlink_to(target)
    with pytest.raises((ValueError, OSError)):
        check.save("run.json", {})
    assert target.read_text() == "preserve"


@pytest.mark.parametrize("change", ["tenant", "missing", "reordered", "duplicate_repo"])
def test_other_scope_cannot_be_selected(change):
    scope, manifest = fixture_scope()
    if change == "tenant":
        manifest["fixtures"][0]["tenant"] = str(uuid4())
    elif change == "missing":
        manifest["fixtures"].pop()
    elif change == "reordered":
        manifest["fixtures"].reverse()
    else:
        manifest["fixtures"][1]["repository"] = manifest["fixtures"][0]["repository"]
    with pytest.raises(ValueError):
        check.scope_check(manifest, scope)


def test_selected_versions_are_derived_and_ingest_kind_is_bound():
    scope, manifest = fixture_scope()
    check.scope_check(manifest, scope)
    targets = check.selected(manifest)
    tenant_ids = tuple(UUID(r["tenant"]) for r in scope)
    queue = check.SelectedQueue(object(), tenant_ids, targets)
    compiled = queue._scope().compile(dialect=postgresql.dialect())
    values = list(compiled.params.values())
    assert "INGEST" in values and "EMBED" not in values
    assert all(doc in values and version in values for _tenant, doc, version in targets)
    assert all(str(doc) not in str(compiled) for _tenant, doc, _version in targets)


@pytest.mark.parametrize("change", ["case", "extra", "actor"])
def test_only_explicit_new_txt_case_is_admitted(change):
    _scope, manifest = fixture_scope()
    item = manifest["fixtures"][0]["documents"][0]
    if change == "extra":
        manifest["fixtures"][0]["documents"].append(item.copy())
    else:
        item["case" if change == "case" else "actor"] = "other"
    with pytest.raises(ValueError):
        check.selected(manifest)


def test_duplicate_or_outside_queue_targets_are_refused():
    scope, manifest = fixture_scope()
    targets = check.selected(manifest)
    tenant_ids = tuple(UUID(r["tenant"]) for r in scope)
    with pytest.raises(ValueError):
        check.SelectedQueue(object(), tenant_ids, targets[:1] * 4)
    with pytest.raises(ValueError):
        check.SelectedQueue(object(), tenant_ids, ((uuid4(), uuid4(), uuid4()),) + targets[1:])


def test_manifest_cannot_substitute_another_corpus():
    _scope, manifest = fixture_scope()
    manifest["fixtures"][0]["documents"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError):
        check.selected(manifest)
