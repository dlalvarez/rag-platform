"""Run the F03 policy proof in disposable containers on a dedicated internal network."""

import os
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

import f01_host

BAO_IMAGE = (
    "ghcr.io/openbao/openbao:2.7.2@sha256:"
    "5046911075e137e154ce49ab051502f4ec7cf367d484ae4a4dce665d9b90561f"
)


def docker(*args, check=True, **kwargs):
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, check=check, timeout=240, **kwargs
    )


def main():
    f01_host.validate_host(starting=True)
    uid = f"{os.getuid()}:{os.getgid()}"
    name = "rag-f03-app-proof-" + uuid4().hex
    network, server = name + "-net", name + "-bao"
    try:
        with tempfile.TemporaryDirectory(prefix=name + "-") as folder:
            config = Path(folder) / "openbao.hcl"
            config.write_text("""ui = false
disable_mlock = true
api_addr = "https://openbao:8200"
storage "inmem" {}
listener "tcp" {
  address = "0.0.0.0:8200"
  tls_cert_file = "/tls/openbao.crt"
  tls_key_file = "/tls/openbao.key"
  tls_min_version = "tls13"
  disable_unauthed_generate_root_endpoints = false
}
""")
            config.chmod(0o600)
            docker("network", "create", "--internal", network)
            tls = "/srv/rag-data/rag-platform/f01/tls"
            docker(
                "run",
                "-d",
                "--name",
                server,
                "--network",
                network,
                "--network-alias",
                "openbao",
                "--user",
                uid,
                "--read-only",
                "--memory",
                "256m",
                "--cpus",
                "0.25",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--mount",
                f"type=bind,src={config},dst=/config/openbao.hcl,readonly",
                "--mount",
                f"type=bind,src={tls}/openbao.crt,dst=/tls/openbao.crt,readonly",
                "--mount",
                f"type=bind,src={tls}/openbao.key,dst=/tls/openbao.key,readonly",
                BAO_IMAGE,
                "server",
                "-config=/config/openbao.hcl",
            )
            result = docker(
                "run",
                "--rm",
                "--network",
                network,
                "--user",
                uid,
                "--read-only",
                "--memory",
                "512m",
                "--cpus",
                "0.5",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--env",
                "F03_ISOLATED_PROOF=1",
                "--mount",
                f"type=bind,src={tls}/ca.crt,dst=/run/f01-ca.crt,readonly",
                "--entrypoint",
                "python",
                "rag-f02-tools:t006",
                "scripts/f03_application_proof.py",
                check=False,
            )
            # No raw logs/stderr/exception. Accept only the proof's closed protocol.
            lines = result.stdout.splitlines()
            if (
                result.returncode
                or len(lines) != 3
                or not all(line.startswith("PASS F03 APP PROOF: ") for line in lines)
            ):
                raise RuntimeError("ISOLATED_PROOF_REFUSED")
            for line in lines:
                print(line)
    finally:
        docker("rm", "-f", server, check=False)
        docker("network", "rm", network, check=False)


if __name__ == "__main__":
    try:
        main()
    except (Exception, KeyboardInterrupt):
        raise SystemExit("F03 APP PROOF HOST REFUSED; sin salida sensible.") from None
