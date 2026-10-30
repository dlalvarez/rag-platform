"""Interactive OpenBao bootstrap. Init/unseal/passwords require the operator's own TTY."""

import argparse
import getpass
import logging
import os
import ssl
import sys
import time
from pathlib import Path
from uuid import UUID

import httpx

from rag_platform.providers.secrets import Credential, OpenBaoSecretStore, SecretStoreError

ROOT = Path(__file__).resolve().parents[1]
CANARY = UUID("e2fc03f9-a253-4b02-8592-ff00409567b5")
CA = Path(os.environ.get("BAO_CACERT", "/run/f01-ca.crt"))
ENDPOINT = "https://openbao:8200"


class OperatorFailure(RuntimeError):
    MESSAGES = {
        "CONNECTION": "No se pudo completar la conexión TLS con OpenBao.",
        "UNSEAL_REJECTED": (
            "OpenBao rechazó la clave de desbloqueo. Copia únicamente la clave original "
            "completa en una línea; no uses la contraseña del operador ni el token root."
        ),
        "KEY_EMPTY": "No se recibió una clave de desbloqueo.",
        "KEY_FORMAT": "La clave contiene espacios o saltos de línea internos. Revisa la copia.",
        "NOT_INITIALIZED": "OpenBao no está inicializado. Detente y revisa el estado con Codex.",
        "SEALED": "OpenBao sigue sellado. Ejecuta unseal antes de check.",
        "UNAVAILABLE": "OpenBao no está disponible o sigue sellado.",
        "AUTH": "OpenBao rechazó la autenticación; no se muestran valores ni respuestas.",
        "API": "OpenBao rechazó la operación; no se muestra el cuerpo de respuesta.",
        "RESPONSE": "OpenBao devolvió una respuesta inesperada.",
        "EXPIRY": "No se pudo demostrar la caducidad real del token. No se marca PASS.",
    }

    def __init__(self, code: str, status: int | None = None) -> None:
        message = self.MESSAGES[code]
        suffix = f" HTTP {status}." if type(status) is int and 100 <= status <= 599 else ""
        super().__init__(f"F01-{code}: {message}{suffix}")
        self.code = code


def require_unsealed(http: httpx.Client) -> None:
    status = call(http, "GET", "sys/seal-status")
    if not status["initialized"]:
        raise OperatorFailure("NOT_INITIALIZED")
    if status["sealed"]:
        raise OperatorFailure("SEALED")


def unseal_operator(http: httpx.Client) -> None:
    tty_required()
    status = call(http, "GET", "sys/seal-status")
    if not status["initialized"]:
        raise OperatorFailure("NOT_INITIALIZED")
    if not status["sealed"]:
        print("OpenBao ya está desbloqueado.")
        return
    key = getpass.getpass("Clave de desbloqueo original (una línea): ").strip()
    if not key:
        raise OperatorFailure("KEY_EMPTY")
    if any(character.isspace() for character in key):
        raise OperatorFailure("KEY_FORMAT")
    result = call(http, "POST", "sys/unseal", payload={"key": key})
    del key
    if result["sealed"]:
        raise OperatorFailure("SEALED")
    print("Desbloqueado.")


def check_existing(http: httpx.Client) -> None:
    tty_required()
    require_unsealed(http)
    check_runtime(http, login_operator(http))


def client() -> httpx.Client:
    return httpx.Client(
        base_url=ENDPOINT,
        verify=ssl.create_default_context(cafile=str(CA)),
        timeout=10,
        trust_env=False,
        follow_redirects=False,
    )


def call(
    http: httpx.Client,
    method: str,
    path: str,
    token: str | None = None,
    payload: dict | None = None,
) -> dict:
    try:
        response = http.request(
            method, "/v1/" + path, headers={"X-Vault-Token": token} if token else {}, json=payload
        )
    except httpx.HTTPError:
        raise OperatorFailure("CONNECTION") from None
    status = response.status_code
    if status not in (200, 204):
        if path == "sys/unseal" and status == 400:
            raise OperatorFailure("UNSEAL_REJECTED", status)
        if status == 503:
            raise OperatorFailure("UNAVAILABLE", status)
        if status in (401, 403) or (
            status == 400 and path in ("auth/userpass/login/diego", "auth/approle/login")
        ):
            raise OperatorFailure("AUTH", status)
        raise OperatorFailure("API", status)
    try:
        result = response.json() if response.content else {}
        if not isinstance(result, dict):
            raise ValueError
        return result
    except ValueError:
        raise OperatorFailure("RESPONSE") from None


def tty_required() -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError(
            "Use your own interactive SSH terminal; no redirected output or automation"
        )


def new_operator_password() -> str:
    while True:
        password = getpass.getpass(
            "Nueva contraseña del operador diego (mínimo 16 caracteres; guardar en el gestor): "
        )
        if len(password) < 16:
            print("La contraseña necesita al menos 16 caracteres. Inténtalo de nuevo.")
            continue
        if password != getpass.getpass("Repite la contraseña: "):
            print("Las contraseñas no coinciden. Inténtalo de nuevo.")
            continue
        return password


def login_operator(http: httpx.Client) -> str:
    password = getpass.getpass("Contraseña del operador diego: ")
    result = call(http, "POST", "auth/userpass/login/diego", payload={"password": password})
    return result["auth"]["client_token"]


def check_runtime(http: httpx.Client, operator: str, *, initialize_canary: bool = False) -> None:
    own = call(http, "GET", "auth/token/lookup-self", operator)["data"]
    if set(own["policies"]) != {"default", "f01-operator"}:
        raise RuntimeError("Unexpected operator policies")
    response = http.get("/v1/sys/mounts", headers={"X-Vault-Token": operator})
    if response.status_code != 403:
        raise RuntimeError("Operator unexpectedly has system administration")
    role = call(http, "GET", "auth/approle/role/f01-cli/role-id", operator)["data"]["role_id"]
    secret_id = call(http, "POST", "auth/approle/role/f01-cli/secret-id", operator, {})["data"][
        "secret_id"
    ]
    with OpenBaoSecretStore(ENDPOINT, CA) as store:
        store.login(role, secret_id)
        # A used one-use SecretID must be denied by the actual service.
        rejected = http.post(
            "/v1/auth/approle/login", json={"role_id": role, "secret_id": secret_id}
        )
        if rejected.status_code not in (400, 403):
            raise RuntimeError("AppRole accepted a consumed SecretID")
        from rag_platform.tenancy.contracts import SecretRef

        try:
            existing = store.read(SecretRef(CANARY, 1))
            if existing != Credential("f01-canary", "synthetic-not-an-account"):
                raise RuntimeError("Unexpected canary ownership; stop for review")
            version = SecretRef(CANARY, 1)
        except SecretStoreError as error:
            if error.code.value != "SECRET_NOT_FOUND" or not initialize_canary:
                raise
            version = store.write(
                CANARY, Credential("f01-canary", "synthetic-not-an-account"), expected_version=0
            )
        if store.read(version) != Credential("f01-canary", "synthetic-not-an-account"):
            raise RuntimeError("Canary read mismatch")
        try:
            store.write(
                CANARY, Credential("f01-canary", "synthetic-not-an-account"), expected_version=0
            )
        except SecretStoreError as error:
            if error.code.value != "SECRET_CONFLICT":
                raise
        else:
            raise RuntimeError("CAS did not reject a duplicate creation")
    print("PASS: operador limitado, AppRole sin root, SecretID de un uso, KV versionado y CAS.")
    call(http, "POST", "auth/token/revoke-self", operator, {})


def check_expiry(http: httpx.Client) -> None:
    """Shorten only this test session via renew-self; never change roles or policies."""
    tty_required()
    require_unsealed(http)
    operator = login_operator(http)
    own = call(http, "GET", "auth/token/lookup-self", operator)["data"]
    if set(own["policies"]) != {"default", "f01-operator"}:
        raise OperatorFailure("AUTH")
    role = call(http, "GET", "auth/approle/role/f01-cli/role-id", operator)["data"]["role_id"]
    secret_id = call(http, "POST", "auth/approle/role/f01-cli/secret-id", operator, {})["data"][
        "secret_id"
    ]
    auth = call(
        http, "POST", "auth/approle/login", payload={"role_id": role, "secret_id": secret_id}
    )["auth"]
    del secret_id
    if (
        set(auth["policies"]) != {"default", "f01-provisioner"}
        or not isinstance(auth["client_token"], str)
        or not auth["client_token"]
    ):
        raise OperatorFailure("AUTH")
    token = auth["client_token"]
    del auth
    response = http.get(
        f"/v1/f01/data/{CANARY}", params={"version": 1}, headers={"X-Vault-Token": token}
    )
    if response.status_code != 200:
        raise OperatorFailure("EXPIRY", response.status_code)
    data = response.json()["data"]
    if data["metadata"]["version"] != 1 or data["data"] != {
        "username": "f01-canary",
        "password": "synthetic-not-an-account",
    }:
        raise OperatorFailure("EXPIRY")
    # Remove operator session before waiting. AppRole login was a separate, unauthenticated
    # request, so this is not revoking the AppRole token whose natural expiry is tested.
    call(http, "POST", "auth/token/revoke-self", operator, {})
    del operator
    renewed = call(http, "POST", "auth/token/renew-self", token, {"increment": "2s"})["auth"]
    ttl = renewed["lease_duration"]
    if (
        type(ttl) is not int
        or not 0 < ttl <= 900
        or renewed["client_token"] != token
        or set(renewed["policies"]) != {"default", "f01-provisioner"}
    ):
        raise OperatorFailure("EXPIRY")
    del renewed
    print(f"Lectura previa correcta. Esperando caducidad real: {ttl + 2} segundos.", flush=True)
    time.sleep(ttl + 2)
    expired = http.get(
        f"/v1/f01/data/{CANARY}", params={"version": 1}, headers={"X-Vault-Token": token}
    )
    del token
    require_unsealed(http)
    if expired.status_code != 403:
        raise OperatorFailure("EXPIRY", expired.status_code)
    print("PASS: token AppRole caducado rechazado por OpenBao (HTTP 403); nodo desbloqueado.")


def bootstrap(http: httpx.Client, *, resume: bool) -> None:
    tty_required()
    status = call(http, "GET", "sys/seal-status")
    if resume:
        if not status["initialized"] or status["sealed"]:
            raise RuntimeError("Resume requires an initialized, unsealed OpenBao")
        root_token = getpass.getpass("Token root temporal de esta inicialización: ")
    else:
        if status["initialized"]:
            raise RuntimeError("Already initialized: never reinitialize or erase Raft")
        if input("¿Gestor y copia fuera de línea preparados? Escribe PREPARADOS: ") != "PREPARADOS":
            raise RuntimeError("Custody preparation not confirmed")
        initialized = call(
            http,
            "POST",
            "sys/init",
            payload={
                "secret_shares": 1,
                "secret_threshold": 1,
            },
        )
        key = initialized["keys_base64"][0]
        root_token = initialized["root_token"]
        print("\nCLAVE DE DESBLOQUEO (guárdala en gestor y copia fuera de línea):\n" + key)
        print("\nTOKEN ROOT TEMPORAL (guardar solo hasta completar bootstrap):\n" + root_token)
        if (
            input("\nConfirma GUARDADAS cuando ambas copias y el token temporal estén guardados: ")
            != "GUARDADAS"
        ):
            raise RuntimeError("Stopped. Keep the displayed material; do not initialize again")
        unsealed = call(http, "POST", "sys/unseal", payload={"key": key})
        if unsealed["sealed"]:
            raise RuntimeError("OpenBao remains sealed")
        del key, initialized
    identity = call(http, "GET", "auth/token/lookup-self", root_token)["data"]
    if "root" not in identity["policies"]:
        raise RuntimeError("Bootstrap requires the temporary initialization root")
    mounts = call(http, "GET", "sys/mounts", root_token)
    mounts = mounts.get("data", mounts)
    if "f01/" not in mounts:
        call(
            http, "POST", "sys/mounts/f01", root_token, {"type": "kv", "options": {"version": "2"}}
        )
    elif mounts["f01/"]["type"] != "kv" or mounts["f01/"]["options"].get("version") != "2":
        raise RuntimeError("Existing f01 mount incompatible; stop without replacing it")
    call(http, "POST", "f01/config", root_token, {"cas_required": True, "max_versions": 10})
    auth = call(http, "GET", "sys/auth", root_token)
    auth = auth.get("data", auth)
    for name in ("approle", "userpass"):
        if name + "/" not in auth:
            call(http, "POST", "sys/auth/" + name, root_token, {"type": name})
        elif auth[name + "/"]["type"] != name:
            raise RuntimeError("Existing authentication mount incompatible")
    for name in ("provisioner", "operator"):
        policy = (ROOT / "ops/f01" / f"{name}.hcl").read_text()
        call(http, "PUT", "sys/policies/acl/f01-" + name, root_token, {"policy": policy})
    call(
        http,
        "POST",
        "auth/approle/role/f01-cli",
        root_token,
        {
            "bind_secret_id": True,
            "secret_id_ttl": "10m",
            "secret_id_num_uses": 1,
            "token_policies": ["f01-provisioner"],
            "token_ttl": "15m",
            "token_max_ttl": "60m",
            "token_explicit_max_ttl": "60m",
        },
    )
    password = new_operator_password()
    call(
        http,
        "POST",
        "auth/userpass/users/diego",
        root_token,
        {
            "password": password,
            "token_policies": ["f01-operator"],
            "token_ttl": "15m",
            "token_max_ttl": "60m",
        },
    )
    del password
    check_runtime(http, login_operator(http), initialize_canary=True)
    call(http, "POST", "auth/token/revoke-self", root_token, {})
    revoked = http.get("/v1/auth/token/lookup-self", headers={"X-Vault-Token": root_token})
    if revoked.status_code != 403:
        raise RuntimeError("Could not verify temporary root revocation")
    del root_token
    print(
        "PASS: root inicial revocado. Elimina su copia temporal; conserva la clave de desbloqueo."
    )
    print("No pegues la salida ni secretos en chat. Informa únicamente: bootstrap completado.")


def main() -> None:
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("status", "init", "resume", "unseal", "check", "check-expiry")
    )
    args = parser.parse_args()
    try:
        with client() as http:
            if args.command == "status":
                result = call(http, "GET", "sys/seal-status")
                print({key: result[key] for key in ("initialized", "sealed", "t", "n")})
            elif args.command in ("init", "resume"):
                bootstrap(http, resume=args.command == "resume")
            elif args.command == "unseal":
                unseal_operator(http)
            elif args.command == "check-expiry":
                check_expiry(http)
            else:
                check_existing(http)
    except OperatorFailure as error:
        raise SystemExit(str(error)) from None
    except SecretStoreError as error:
        raise SystemExit(
            f"F01-SECRET: {error.code.value}. No se muestran valores secretos."
        ) from None
    except httpx.HTTPError:
        raise SystemExit(
            "F01-CONNECTION: conexión TLS interrumpida; no se muestran detalles."
        ) from None
    except (Exception, KeyboardInterrupt):
        # No traceback, exception message, HTTP body or initialization response.
        raise SystemExit(
            "Operación detenida. Conserva el material ya mostrado; consulta el runbook."
        ) from None


if __name__ == "__main__":
    main()
