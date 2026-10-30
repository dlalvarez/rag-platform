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

    def runtime_failure(http, token, **kwargs):
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


def test_recovery_check_cannot_recreate_missing_canary(monkeypatch):
    from rag_platform.providers.secrets import SecretErrorCode, SecretStoreError

    class MissingCanary:
        def __init__(self, *args):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def login(self, *args):
            pass

        def read(self, ref):
            raise SecretStoreError(SecretErrorCode.NOT_FOUND)

        def write(self, *args, **kwargs):
            raise AssertionError("Recovery must never recreate a missing canary")

    class DeniedResponse:
        status_code = 403

    class Http:
        def get(self, *args, **kwargs):
            return DeniedResponse()

        def post(self, *args, **kwargs):
            return DeniedResponse()

    def fake_call(http, method, path, token=None, payload=None):
        if path == "auth/token/lookup-self":
            return {"data": {"policies": ["default", "f01-operator"]}}
        if path.endswith("role-id"):
            return {"data": {"role_id": "synthetic-role"}}
        if path.endswith("secret-id"):
            return {"data": {"secret_id": "synthetic-one-use-id"}}
        raise AssertionError("Unexpected recovery request")

    monkeypatch.setattr(operator, "OpenBaoSecretStore", MissingCanary)
    monkeypatch.setattr(operator, "call", fake_call)
    with pytest.raises(SecretStoreError) as error:
        operator.check_runtime(Http(), "synthetic-operator")
    assert error.value.code == SecretErrorCode.NOT_FOUND


def test_unseal_http_error_is_actionable_without_echoing_any_secret():
    import httpx

    marker = "synthetic-value-never-echo"
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(400, json={"errors": [marker]})
        ),
        base_url="https://openbao:8200",
    ) as http:
        with pytest.raises(operator.OperatorFailure) as error:
            operator.call(http, "POST", "sys/unseal", payload={"key": marker})
    assert error.value.code == "UNSEAL_REJECTED"
    assert "HTTP 400" in str(error.value)
    assert marker not in str(error.value)


def test_connection_exception_is_sanitized():
    import httpx

    marker = "synthetic-sensitive-transport-detail"

    def fail(request):
        raise httpx.ReadTimeout(marker)

    with httpx.Client(transport=httpx.MockTransport(fail), base_url="https://openbao:8200") as http:
        with pytest.raises(operator.OperatorFailure) as error:
            operator.call(http, "POST", "sys/unseal", payload={"key": marker})
    assert error.value.code == "CONNECTION"
    assert marker not in str(error.value)
    assert error.value.__cause__ is None


def test_check_does_not_ask_for_password_while_sealed(monkeypatch):
    monkeypatch.setattr(operator, "tty_required", lambda: None)
    monkeypatch.setattr(operator, "call", lambda *a, **kw: {"initialized": True, "sealed": True})

    def never_prompt(*args):
        raise AssertionError("Do not request a password for a sealed server")

    monkeypatch.setattr(operator.getpass, "getpass", never_prompt)
    with pytest.raises(operator.OperatorFailure) as error:
        operator.check_existing(object())
    assert error.value.code == "SEALED"


@pytest.mark.parametrize(("typed", "code"), [("  ", "KEY_EMPTY"), ("synthetic key", "KEY_FORMAT")])
def test_invalid_key_format_never_sent_or_echoed(monkeypatch, capsys, typed, code):
    monkeypatch.setattr(operator, "tty_required", lambda: None)
    monkeypatch.setattr(operator.getpass, "getpass", lambda prompt: typed)
    calls = []

    def fake_call(http, method, path, **kwargs):
        calls.append(path)
        assert path == "sys/seal-status"
        return {"initialized": True, "sealed": True}

    monkeypatch.setattr(operator, "call", fake_call)
    with pytest.raises(operator.OperatorFailure) as error:
        operator.unseal_operator(object())
    assert error.value.code == code
    assert calls == ["sys/seal-status"]
    assert capsys.readouterr().out == ""


def test_unseal_trims_only_surrounding_copy_whitespace(monkeypatch, capsys):
    monkeypatch.setattr(operator, "tty_required", lambda: None)
    monkeypatch.setattr(operator.getpass, "getpass", lambda prompt: "  synthetic-key\t")
    calls = []

    def fake_call(http, method, path, **kwargs):
        calls.append(path)
        if path == "sys/seal-status":
            return {"initialized": True, "sealed": True}
        assert kwargs["payload"] == {"key": "synthetic-key"}
        return {"sealed": False}

    monkeypatch.setattr(operator, "call", fake_call)
    operator.unseal_operator(object())
    assert calls == ["sys/seal-status", "sys/unseal"]
    assert capsys.readouterr().out == "Desbloqueado.\n"
