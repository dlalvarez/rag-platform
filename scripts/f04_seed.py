"""Limited synthetic F04 seeding: HTTPS originals, explicit authorized intents, no day/admin."""

import argparse
import hashlib
import io
import json
import logging
import os
import stat
from pathlib import Path
from uuid import UUID, uuid4

from f02_testing import Humans
from f03_http_check import API
from f03_testing import real_actors
from f04_corpus import corpus, pdf
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

from rag_platform.identity_api import private_file
from rag_platform.ingestion import journal
from rag_platform.ingestion.extraction import ExtractionError
from rag_platform.ingestion.extractor import extract
from rag_platform.ingestion.runtime import Runtime
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.postgres import Target
from rag_platform.tenancy.resolver import control_engine

CA = Path("/run/f01-ca.crt")
ROOT = Path(__file__).resolve().parents[1]
OUT = Path("/run/f04-qa")
PHASE = "START"


def save(name, value):
    data = (json.dumps(value, sort_keys=True) + "\n").encode()
    fd = os.open(OUT / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def malformed():
    reader = PdfReader(io.BytesIO(pdf()))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 250 Td <not-hex> Tj ET")
    writer.pages[1][NameObject("/Contents")] = writer._add_object(stream)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def run():
    global PHASE
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=UUID, required=True)
    args = parser.parse_args()
    info = OUT.lstat()
    assert stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
    assert stat.S_IMODE(info.st_mode) == 0o700 and OUT.resolve() == OUT
    save("started.json", {"version": 1, "run_id": str(args.run), "state": "STARTED"})
    humans, api, runtime, control = None, None, None, None
    try:
        PHASE = "IDENTITY"
        humans = Humans()
        humans.ready()
        api = API(humans)
        credential = Credential(
            "f02_identity_app", private_file("/run/secrets/identity_app_password", 4096).decode()
        )
        control = control_engine(Target("postgres", 5432, CA), credential)
        key = private_file("/run/secrets/api_authority_key", 32)
        runtime = Runtime(
            control,
            key,
            Path("/run/f04-worker"),
            "https://openbao:8200",
            CA,
            ROOT / "ops/f03/application-scope.json",
        )
        runtime.preflight()
        actors = real_actors(control, humans)
        fixtures = json.loads((ROOT / "ops/f03/application-scope.json").read_text())["fixtures"]
        values = {"positive-" + kind: (mime, body) for kind, (mime, body) in corpus().items()}
        values.update(
            {
                "scan": ("application/pdf", pdf(("scan",), scanned=True)),
                "malformed": ("application/pdf", malformed()),
                "encrypted": ("application/pdf", pdf(("secret fixture",), encrypted=True)),
            }
        )
        for case in ("crash", "stop", "tombstone", "acl", "membership", "dependency"):
            values[case] = (
                "text/plain",
                ("F04_WORKER_PRIVATE_CANARY " + case + " SELECT valor FROM tabla;\n").encode(),
            )
        # Confirm the malformed fixture has a readable first page and fails its
        # second page in the real isolated extractor; no partial result may escape.
        PHASE = "MALFORMED_CONTROL"
        import tempfile

        body = values["malformed"][1]
        assert PdfReader(io.BytesIO(body)).pages[0].extract_text().strip()
        with tempfile.TemporaryFile("w+b") as stream:
            stream.write(body)
            stream.flush()
            try:
                extract(
                    stream,
                    "application/pdf",
                    expected_size=len(body),
                    expected_hash=hashlib.sha256(body).hexdigest(),
                )
            except ExtractionError as error:
                assert error.code == "PARSER_INVALID"
            else:
                raise RuntimeError("MALFORMED_FIXTURE_NOT_ENFORCED")
        result = {
            "version": 1,
            "run_id": str(args.run),
            "actors": {k: str(v) for k, v in actors.items()},
            "fixtures": [],
        }
        for fixture in fixtures:
            PHASE = fixture["name"].upper() + "/REPOSITORY"
            tenant = UUID(fixture["tenant"])
            base = "/api/v1/tenants/" + str(tenant) + "/repositories"
            created = api.json(
                "alice",
                "POST",
                base,
                value={"name": "f04-worker-" + fixture["name"] + "-" + args.run.hex[:12]},
                expected=201,
            )["repository"]
            repo = UUID(created["repository_id"])
            record = {
                "name": fixture["name"],
                "tenant": str(tenant),
                "repository": str(repo),
                "documents": [],
            }
            save("repository-" + fixture["name"] + ".json", record)
            for user, role in (("bob", "editor"), ("carol", "reader")):
                api.json(
                    "alice",
                    "PUT",
                    base + "/" + str(repo) + "/acl/" + str(actors[user]),
                    value={"role": role},
                )
            for case, (mime, body) in values.items():
                PHASE = fixture["name"].upper() + "/" + case.upper()
                extension = {
                    "application/pdf": "pdf",
                    "text/plain": "txt",
                    "text/markdown": "md",
                }.get(mime, "docx")
                filename = "f04-" + case + "." + extension
                endpoint = base + "/" + str(repo) + "/documents?filename=" + filename
                headers = {
                    "Content-Type": mime,
                    "Idempotency-Key": "f04-" + args.run.hex + "-" + fixture["name"] + "-" + case,
                }
                doc = api.json("alice", "POST", endpoint, body=body, headers=headers, expected=201)[
                    "document"
                ]
                repeated = api.json("alice", "POST", endpoint, body=body, headers=headers)[
                    "document"
                ]
                assert repeated == doc and doc["sha256"] == hashlib.sha256(body).hexdigest()
                item = {
                    "case": case,
                    "mime": mime,
                    "document": doc["document_id"],
                    "original": doc["version_id"],
                    "sha256": doc["sha256"],
                    "byte_size": len(body),
                    "actor": "bob" if case in {"acl", "membership"} else "alice",
                }
                record["documents"].append(item)
                save("document-" + fixture["name"] + "-" + case + ".json", item)
                if case.startswith("positive-"):
                    trace = uuid4()
                    context = runtime.authority.authorize(actors["alice"], tenant, trace)
                    with (
                        runtime.repositories.connections.connection(context, trace) as c,
                        c.begin(),
                    ):
                        plan = journal.request(
                            c, actors["alice"], repo, UUID(item["document"]), trace
                        )
                        assert (
                            journal.request(
                                c, actors["alice"], repo, UUID(item["document"]), uuid4()
                            )
                            == plan
                        )
            result["fixtures"].append(record)
            print(
                "PASS F04 SEED "
                + fixture["name"].upper()
                + ": originales HTTPS/replay y cuatro intenciones."
            )
        save("manifest.json", result)
        print("PASS F04 SEED: manifiesto solo IDs/hashes sintéticos; sin secretos/día/admin.")
    finally:
        if runtime is not None:
            runtime.close()
        if control is not None:
            control.dispose()
        if api is not None:
            api.close()
        if humans is not None:
            humans.close()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    try:
        run()
    except Exception as error:
        print("F04-SEED " + PHASE + " " + type(error).__name__ + " REFUSED; recursos conservados.")
        raise SystemExit(1) from None
