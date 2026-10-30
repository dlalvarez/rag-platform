"""Bootstrap must reject automation before it can generate initialization material."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[3] / "scripts/f01_operator.py"
spec = importlib.util.spec_from_file_location("f01_operator", SCRIPT)
operator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)


def test_no_init_without_own_terminal(monkeypatch):
    monkeypatch.setattr(operator.sys.stdin, "isatty", lambda: False)

    class NeverContact:
        def request(self, *args, **kwargs):
            raise AssertionError("Must not contact initialization API")

    with pytest.raises(RuntimeError, match="interactive"):
        operator.bootstrap(NeverContact(), resume=False)


def test_bootstrap_refuses_wrong_custody_confirmation_before_init(monkeypatch):
    monkeypatch.setattr(operator.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(operator.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt: "no")
    calls = []

    def fake_call(http, method, path, token=None, payload=None):
        calls.append(path)
        if path != "sys/seal-status":
            raise AssertionError("Initialization must not run")
        return {"initialized": False, "sealed": True}

    monkeypatch.setattr(operator, "call", fake_call)
    with pytest.raises(RuntimeError, match="Custody"):
        operator.bootstrap(object(), resume=False)
    assert calls == ["sys/seal-status"]


def test_root_is_not_revoked_if_runtime_validation_fails(monkeypatch):
    monkeypatch.setattr(operator.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(operator.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr(operator.getpass, "getpass", lambda prompt: "synthetic-long-password")
    calls = []

    def fake_call(http, method, path, token=None, payload=None):
        calls.append(path)
        if path == "sys/seal-status":
            return {"initialized": True, "sealed": False}
        if path == "auth/token/lookup-self":
            return {"data": {"policies": ["root"]}}
        if path in {"sys/mounts", "sys/auth"}:
            return {}
        return {}

    monkeypatch.setattr(operator, "call", fake_call)
    monkeypatch.setattr(operator, "login_operator", lambda http: "synthetic-operator")

    def runtime_failure(http, token):
        raise RuntimeError("Synthetic runtime verification failure")

    monkeypatch.setattr(operator, "check_runtime", runtime_failure)
    with pytest.raises(RuntimeError, match="runtime verification"):
        operator.bootstrap(object(), resume=True)
    assert "auth/token/revoke-self" not in calls


def test_short_password_explains_requirement_and_allows_retry(monkeypatch, capsys):
    short = "synthetic"
    valid = "synthetic-valid-password"
    answers = iter((short, valid, valid))
    monkeypatch.setattr(operator.getpass, "getpass", lambda prompt: next(answers))
    assert operator.new_operator_password() == valid
    output = capsys.readouterr().out
    assert "al menos 16 caracteres" in output
    assert short not in output
    assert valid not in output


def test_password_mismatch_allows_retry_without_echo(monkeypatch, capsys):
    valid = "synthetic-valid-password"
    different = "synthetic-other-password"
    answers = iter((valid, different, valid, valid))
    monkeypatch.setattr(operator.getpass, "getpass", lambda prompt: next(answers))
    assert operator.new_operator_password() == valid
    output = capsys.readouterr().out
    assert "no coinciden" in output
    assert valid not in output
    assert different not in output
