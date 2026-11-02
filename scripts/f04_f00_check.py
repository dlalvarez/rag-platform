"""F00 regression in its isolated smoke image; retain a new synthetic SQL/S3 fixture."""

import argparse
import io
import json
from pathlib import Path
from urllib.request import urlopen
from uuid import UUID

import psycopg
from minio import Minio
from psycopg import sql
from urllib3 import PoolManager, Timeout

PAYLOAD = b"F04 retained synthetic F00 regression fixture"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("seed", "verify"))
    p.add_argument("--run", type=UUID, required=True)
    args = p.parse_args()
    table = "f04_regression_" + args.run.hex
    bucket = "f04-regression-" + args.run.hex
    for url in ("http://api:8000/healthz", "http://minio:9000/minio/health/ready"):
        with urlopen(url, timeout=5) as response:
            assert response.status == 200
            if "/healthz" in url:
                assert json.load(response) == {"status": "ok", "phase": "F00"}
    pool = PoolManager(timeout=Timeout(connect=3, read=5), retries=False)
    client = Minio(
        "minio:9000",
        access_key=Path("/run/secrets/minio_user").read_text().strip(),
        secret_key=Path("/run/secrets/minio_password").read_text().strip(),
        secure=False,
        http_client=pool,
    )
    try:
        with psycopg.connect(
            host="postgres",
            dbname="f00_scratch",
            user="f00_dev",
            password=Path("/run/secrets/postgres_password").read_text().strip(),
            connect_timeout=5,
        ) as c:
            assert c.execute("SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector").fetchone() == (1.0,)
            if args.mode == "seed":
                assert c.execute("SELECT to_regclass(%s)", (table,)).fetchone() == (None,)
                assert not client.bucket_exists(bucket)
                c.execute(
                    sql.SQL(
                        "CREATE TABLE {} (id integer PRIMARY KEY, payload text NOT NULL)"
                    ).format(sql.Identifier(table))
                )
                c.execute(
                    sql.SQL("INSERT INTO {} VALUES (1,%s)").format(sql.Identifier(table)),
                    (PAYLOAD.decode(),),
                )
                client.make_bucket(bucket)
                client.put_object(bucket, "fixture.txt", io.BytesIO(PAYLOAD), len(PAYLOAD))
            assert c.execute(
                sql.SQL("SELECT id,payload FROM {}").format(sql.Identifier(table))
            ).fetchall() == [(1, PAYLOAD.decode())]
            response = client.get_object(bucket, "fixture.txt")
            try:
                assert response.read() == PAYLOAD
            finally:
                response.close()
                response.release_conn()
        print(
            "PASS T007 F00: "
            + args.mode
            + "; API/vector/S3 and retained fixture; no old resource modified"
        )
    finally:
        pool.clear()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("F04-T007 F00 REFUSED")
        raise SystemExit(1) from None
