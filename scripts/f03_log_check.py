"""Host-only F03 log/temporary inspection; private material never leaves ragdev01."""

import json
import os
import re
import resource
import stat
import subprocess
from pathlib import Path

from f02_api_log_check import run as identity_logs

ROOT = Path(__file__).resolve().parents[1]


def run():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    path = Path(f"/run/user/{os.getuid()}/rag-f03-application/application.json")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
            or not 1 <= info.st_size <= 8192
        ):
            raise ValueError()
        token = json.load(stream)["token"]
    if not isinstance(token, str) or not 1 <= len(token) <= 4096:
        raise ValueError()
    scope = json.loads((ROOT / "ops/f03/application-scope.json").read_text())["fixtures"]
    forbidden = [
        token,
        "F03 HTTP original fixture.",
        "F03 concurrent HTTP fixture.",
        "F03 lifecycle retained original.",
        "http-fixture.",
    ]
    for item in scope:
        tenant = item["tenant"].replace("-", "")
        forbidden.extend(item["refs"])
        forbidden.extend(("rag_t_" + tenant, "rag-t-" + tenant))
    prefix = token.partition(".")[0]
    patterns = [r"(?i)X-Vault-Token"]
    if "." in token and 1 <= len(prefix) <= 8:
        patterns.append(re.escape(prefix + ".") + r"[A-Za-z0-9_-]{16,}")
    identity_logs(extra_forbidden=forbidden, extra_patterns=patterns)
    source = """import json,os,stat
count=0
for name in os.listdir('/proc/1/fd'):
 try:
  count+=int(os.readlink('/proc/1/fd/'+name).startswith('/tmp/'))
 except FileNotFoundError:pass
v=os.statvfs('/tmp')
print(json.dumps({'temporary_fds':count,'mode':stat.S_IMODE(os.stat('/tmp').st_mode),
                  'bytes':v.f_blocks*v.f_frsize}))
"""
    result = subprocess.run(
        ["docker", "exec", "rag-f02-dev-api-1", "python", "-c", source],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode or json.loads(result.stdout) != {
        "temporary_fds": 0,
        "mode": 0o700,
        "bytes": 64 * 1024 * 1024,
    }:
        raise ValueError()
    print("PASS T007 LOGS: sin secretos/refs/contenido/trazas; 0 temporales; tmpfs 64 MiB.")


if __name__ == "__main__":
    try:
        run()
    except (Exception, KeyboardInterrupt) as error:
        code = "LEAK" if isinstance(error, ValueError) and str(error) == "LEAK" else "REFUSED"
        raise SystemExit(f"F03 T007 LOGS: {code}; sin cuerpo de logs ni secretos.") from None
