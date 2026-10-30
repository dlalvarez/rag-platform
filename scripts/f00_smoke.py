"""Integration probe inside the disposable Compose network."""

import io
import json
import sys
import uuid
from pathlib import Path
from urllib.request import urlopen

import psycopg
from minio import Minio
from urllib3 import PoolManager, Timeout


def probe() -> None:
    for url in ("http://api:8000/healthz", "http://minio:9000/minio/health/ready"):
        with urlopen(url, timeout=5) as response:
            assert response.status == 200
            if "/healthz" in url:
                assert json.load(response) == {"status": "ok", "phase": "F00"}
    password = Path("/run/secrets/postgres_password").read_text().strip()
    with psycopg.connect(
        host="postgres",
        dbname="f00_scratch",
        user="f00_dev",
        password=password,
        connect_timeout=5,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cursor.execute("SELECT '[1,2,3]'::vector <-> '[1,2,4]'::vector")
            assert cursor.fetchone() == (1.0,)
    client = Minio(
        "minio:9000",
        access_key=Path("/run/secrets/minio_user").read_text().strip(),
        secret_key=Path("/run/secrets/minio_password").read_text().strip(),
        secure=False,
        http_client=PoolManager(timeout=Timeout(connect=3, read=5), retries=False),
    )
    bucket = "f00-smoke-" + uuid.uuid4().hex
    payload = b"F00 synthetic integration fixture"
    client.make_bucket(bucket)
    try:
        client.put_object(bucket, "fixture.txt", io.BytesIO(payload), len(payload))
        response = client.get_object(bucket, "fixture.txt")
        try:
            assert response.read() == payload
        finally:
            response.close()
            response.release_conn()
    finally:
        client.remove_object(bucket, "fixture.txt")
        client.remove_bucket(bucket)


def persistence(mode: str) -> None:
    password = Path("/run/secrets/postgres_password").read_text().strip()
    client = Minio(
        "minio:9000",
        access_key=Path("/run/secrets/minio_user").read_text().strip(),
        secret_key=Path("/run/secrets/minio_password").read_text().strip(),
        secure=False,
        http_client=PoolManager(timeout=Timeout(connect=3, read=5), retries=False),
    )
    bucket = "f00-persistence-fixture"
    payload = b"F00 synthetic persistent fixture"
    with psycopg.connect(
        host="postgres", dbname="f00_scratch", user="f00_dev", password=password, connect_timeout=5
    ) as connection:
        with connection.cursor() as cursor:
            if mode == "seed":
                cursor.execute("CREATE TABLE IF NOT EXISTS f00_probe (id integer PRIMARY KEY)")
                cursor.execute("INSERT INTO f00_probe VALUES (1) ON CONFLICT DO NOTHING")
                if not client.bucket_exists(bucket):
                    client.make_bucket(bucket)
                client.put_object(bucket, "fixture.txt", io.BytesIO(payload), len(payload))
            elif mode == "verify":
                cursor.execute("SELECT id FROM f00_probe")
                assert cursor.fetchall() == [(1,)]
                response = client.get_object(bucket, "fixture.txt")
                try:
                    assert response.read() == payload
                finally:
                    response.close()
                    response.release_conn()
            elif mode == "clean":
                cursor.execute("DROP TABLE f00_probe")
                client.remove_object(bucket, "fixture.txt")
                client.remove_bucket(bucket)
            else:
                raise ValueError("Unknown persistence probe")


if __name__ == "__main__":
    try:
        if len(sys.argv) == 1:
            probe()
        else:
            persistence(sys.argv[1])
    except Exception:
        print(
            "F00 integration FAILED: dependency unavailable or assertion failed.", file=sys.stderr
        )
        raise SystemExit(1) from None
    print(
        "F00 integration PASS: "
        + (
            sys.argv[1]
            if len(sys.argv) > 1
            else "API, PostgreSQL/vector and synthetic S3 roundtrip."
        )
    )
