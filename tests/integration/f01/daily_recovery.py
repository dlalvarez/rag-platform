"""Disposable real OpenBao regression for DAY recovery after restart. All state is synthetic."""

import sys


def inside():
    import json
    import secrets
    import sys
    import time
    import traceback
    from pathlib import Path

    sys.path.insert(0, "/app/scripts")
    import f01_daily as daily
    import f01_daily_setup as setup
    from f01_operator import CANARY, call, client

    phase = "WAIT"
    print("CALIBRATION ONLY: isolated synthetic Raft; no existing environment credentials.")
    try:
        with client() as h:
            h.timeout = 60
            for _ in range(30):
                try:
                    state = call(h, "GET", "sys/seal-status")
                    break
                except Exception:
                    time.sleep(0.5)
            else:
                raise RuntimeError("fixture unavailable")
            assert state["initialized"] is False
            phase = "INITIALIZE_FIXTURE"
            material = call(
                h, "POST", "sys/init", payload={"secret_shares": 1, "secret_threshold": 1}
            )
            key = material["keys_base64"][0]
            root = material["root_token"]
            del material
            call(h, "POST", "sys/unseal", payload={"key": key})
            for method in ("approle", "userpass"):
                call(h, "POST", "sys/auth/" + method, root, {"type": method})
            for name in ("operator", "provisioner"):
                policy = Path("/app/ops/f01/" + name + ".hcl").read_text()
                call(h, "PUT", "sys/policies/acl/f01-" + name, root, {"policy": policy})
            call(
                h,
                "POST",
                "auth/approle/role/f01-cli",
                root,
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
            password = secrets.token_urlsafe(32)
            call(
                h,
                "POST",
                "auth/userpass/users/diego",
                root,
                {
                    "password": password,
                    "token_policies": ["f01-operator"],
                    "token_ttl": "15m",
                    "token_max_ttl": "60m",
                },
            )
            call(h, "POST", "sys/mounts/f01", root, {"type": "kv", "options": {"version": "2"}})
            call(
                h,
                "POST",
                "f01/data/" + str(CANARY),
                root,
                {
                    "options": {"cas": 0},
                    "data": {"username": "f01-canary", "password": "synthetic-not-an-account"},
                },
            )
            call(h, "POST", "auth/token/revoke-self", root, {})
            del root
            Path("/run/f01-access/restart.request").touch()
            for _ in range(240):
                if Path("/run/f01-access/restart.done").exists():
                    break
                time.sleep(0.25)
            else:
                raise RuntimeError("fixture restart timeout")
            h.timeout = 10
            for _ in range(40):
                try:
                    state = call(h, "GET", "sys/seal-status")
                    break
                except Exception:
                    time.sleep(0.25)
            phase = "RECOVER_AFTER_RESTART"
            setup.recover(h, key)
            phase = "ACTIVATE"
            result = daily.start(password=password, trial=True)
            del key, password
            phase = "VERIFY"
            daily.verify()
            daily.verify()
            daily.revoke()
            print(
                json.dumps(
                    {"result": "PASS", "phase": "COMPLETE", "duration": result["remaining_seconds"]}
                )
            )
    except BaseException as e:
        frames = [
            {"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
            for f in traceback.extract_tb(e.__traceback__)
        ]
        print(
            json.dumps(
                {
                    "result": "FAIL",
                    "phase": phase,
                    "type": type(e).__name__,
                    "operator_code": getattr(e, "code", None),
                    "stage": getattr(e, "step", None),
                    "frames": frames,
                }
            )
        )
        raise SystemExit(1) from None


def host():
    import os
    import subprocess
    import tempfile
    import time
    import uuid
    from pathlib import Path

    import yaml

    base = Path(__file__).resolve().parents[3]
    image = yaml.safe_load((base / "ops/f01/compose.yaml").read_text())["services"]["openbao"][
        "image"
    ]
    tools = "rag-f01-tools:daily-v1"
    for name in (image, tools):
        subprocess.run(["docker", "image", "inspect", name], check=True, capture_output=True)
    identity = uuid.uuid4().hex[:12]
    network = "rag-day-cal-" + identity
    container = None

    def run(args, **kwargs):
        return subprocess.run(args, check=True, capture_output=True, text=True, **kwargs)

    with tempfile.TemporaryDirectory(prefix="rag-day-cal-") as temp:
        root = Path(temp)
        root.chmod(0o700)
        for folder in ("data", "tls", "access"):
            (root / folder).mkdir(mode=0o700)
        run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-subj",
                "/CN=openbao",
                "-addext",
                "subjectAltName=DNS:openbao",
                "-keyout",
                str(root / "tls/key.pem"),
                "-out",
                str(root / "tls/cert.pem"),
            ]
        )
        (root / "tls/key.pem").chmod(0o600)
        (root / "tls/cert.pem").chmod(0o444)
        (root / "config.hcl").write_text("""ui = false
    api_addr = "https://openbao:8200"
    cluster_addr = "https://openbao:8201"
    storage "raft" {
      path = "/data"
      node_id = "disposable-calibration"
    }
    listener "tcp" {
      address = "0.0.0.0:8200"
      tls_cert_file = "/tls/cert.pem"
      tls_key_file = "/tls/key.pem"
      tls_min_version = "tls13"
      tls_acme_ca_directory = ""
      disable_unauthed_generate_root_endpoints = false
    }
    """)
        (root / "inside.py").write_text(Path(__file__).read_text())
        (root / "inside.py").chmod(0o600)
        run(
            [
                "docker",
                "network",
                "create",
                "--internal",
                "--label",
                "rag.day.calibration=" + identity,
                network,
            ]
        )
        try:
            server = run(
                [
                    "docker",
                    "run",
                    "-d",
                    "--rm",
                    "--pull=never",
                    "--name",
                    network + "-bao",
                    "--label",
                    "rag.day.calibration=" + identity,
                    "--network",
                    network,
                    "--network-alias",
                    "openbao",
                    "--memory",
                    "384m",
                    "--memory-swap",
                    "384m",
                    "--cpus",
                    "0.5",
                    "--user",
                    str(os.getuid()) + ":" + str(os.getgid()),
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges:true",
                    "--mount",
                    "type=bind,src=" + str(root / "data") + ",dst=/data",
                    "--mount",
                    "type=bind,src=" + str(root / "tls") + ",dst=/tls,readonly",
                    "--mount",
                    "type=bind,src=" + str(root / "config.hcl") + ",dst=/config.hcl,readonly",
                    "--entrypoint",
                    "/usr/bin/bao",
                    image,
                    "server",
                    "-config=/config.hcl",
                ]
            )
            container = server.stdout.strip()
            process = subprocess.Popen(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--pull=never",
                    "--network",
                    network,
                    "--label",
                    "rag.day.calibration=" + identity,
                    "--memory",
                    "384m",
                    "--memory-swap",
                    "384m",
                    "--cpus",
                    "0.25",
                    "--user",
                    str(os.getuid()) + ":" + str(os.getgid()),
                    "--cap-drop",
                    "ALL",
                    "--security-opt",
                    "no-new-privileges:true",
                    "--mount",
                    "type=bind,src=" + str(root / "tls/cert.pem") + ",dst=/run/f01-ca.crt,readonly",
                    "--mount",
                    "type=bind,src=" + str(root / "access") + ",dst=/run/f01-access",
                    "--mount",
                    "type=bind,src=" + str(root / "inside.py") + ",dst=/work.py,readonly",
                    "--entrypoint",
                    "python",
                    tools,
                    "/work.py",
                    "--inside",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(240):
                if (root / "access/restart.request").exists():
                    run(["docker", "restart", container])
                    (root / "access/restart.done").touch()
                    break
                if process.poll() is not None:
                    break
                time.sleep(0.25)
            stdout, stderr = process.communicate(timeout=150)
            print(stdout.strip())
            print("CALIBRATION_EXIT", process.returncode)
        finally:
            owned = subprocess.run(
                ["docker", "ps", "-aq", "--filter", "label=rag.day.calibration=" + identity],
                capture_output=True,
                text=True,
            )
            for owned_id in owned.stdout.split():
                subprocess.run(["docker", "rm", "-f", owned_id], capture_output=True)
            subprocess.run(["docker", "network", "rm", network], capture_output=True)
    print("CLEANUP: disposable server/network/TLS/data removed; no production mounts used.")

    if process.returncode:
        raise SystemExit(process.returncode)


if __name__ == "__main__":
    if sys.argv[1:] == ["--inside"]:
        inside()
    elif sys.argv[1:] == ["--run"]:
        host()
    else:
        raise SystemExit("Use --run only on the authorized development host.")
