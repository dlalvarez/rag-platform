"""Controlled F05 development adoption. No new tenants, secrets, or destructive rollback."""

import argparse
import json
import logging
import os
import re
import stat
from pathlib import Path
from uuid import UUID, uuid5

import sqlalchemy as sa
from f01_admin import DAY_ACTOR
from f01_daily import session
from f02_common import credential, engine
from f03_fixtures import ROOT, snapshot
from f03_schema_check import connection_engine
from f04_adopt import role_login
from f04_schema_check import fingerprint
from sqlalchemy.orm import Session

from rag_platform.control.identity_models import IdentityBase
from rag_platform.control.models import DbLocation, Instance, ProvisioningOperation, Tenant
from rag_platform.embeddings.migrations import (
    VERSION,
    apply_spaces,
    migrate_spaces_controlled,
    register_space,
)
from rag_platform.embeddings.qwen import qwen_profile
from rag_platform.embeddings.space_ddl import table_name
from rag_platform.identity_api import private_file
from rag_platform.ingestion.queue_schema import jobs
from rag_platform.ingestion.schema_f04_0003 import build_metadata
from rag_platform.providers.secrets import Credential
from rag_platform.provisioning.migration_control import migrate_controlled
from rag_platform.provisioning.migrations import MigrationError, migration_session
from rag_platform.provisioning.postgres import Names, Target
from rag_platform.tenancy.contracts import SecretRef
from rag_platform.tenancy.resolver import AdministrativeTenant, CatalogResolver, TenantAccessError

CA = Path("/run/f01-ca.crt")
OUT = Path("/run/f05-qa")
PHASE = "START"


def save(name, value):
    encoded = json.dumps(value, sort_keys=True) + "\n"
    path = OUT / name
    if path.exists():
        if private_file(path, 512 * 1024).decode() != encoded:
            raise RuntimeError("CHECKPOINT_CONFLICT")
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())


def target_data(control, tenant):
    with Session(control) as c:
        row, location = c.get(Tenant, tenant), c.get(DbLocation, tenant)
        operation = c.scalar(
            sa.select(ProvisioningOperation).where(ProvisioningOperation.tenant_id == tenant)
        )
        if (
            row is None
            or location is None
            or operation is None
            or row.state == "SUSPENDED"
            or operation.state != "SUCCEEDED"
            or row.desired_version not in ("f04_tenant_0003", VERSION)
            or location.ssl_mode != "verify-full"
        ):
            raise RuntimeError("CATALOG_CONFLICT")
        instance = c.get(Instance, location.instance_id)
        names = Names(tenant, operation.id)
        if (
            instance is None
            or instance.host not in ("postgres", "postgres2")
            or instance.port != 5432
            or location.db_name != names.database
        ):
            raise RuntimeError("CATALOG_CONFLICT")
        refs = {
            kind: SecretRef(
                getattr(location, kind + "_secret_ref"), getattr(location, kind + "_secret_version")
            )
            for kind in ("migrator", "app", "readonly")
        }
        return Target(instance.host, instance.port, CA), names, refs


def run(mode):
    global PHASE
    info = OUT.lstat()
    assert stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid()
    assert stat.S_IMODE(info.st_mode) == 0o700 and OUT.resolve() == OUT
    control = engine("migrator")
    scope = json.loads((ROOT / "ops/f03/application-scope.json").read_text())["fixtures"]
    tenants = tuple(UUID(f["tenant"]) for f in scope)
    assert len(tenants) == len(set(tenants)) == 4
    assert {f["name"] for f in scope} == {"same-a", "same-b", "two-a", "two-b"}
    try:
        legacy_before = {key: value.hex() for key, value in snapshot(control).items()}
        with control.connect() as c:
            identities_before = fingerprint(c, list(IdentityBase.metadata.tables.values()))
            jobs_before = fingerprint(c, [jobs])
            assert (
                c.scalar(
                    sa.select(sa.func.count())
                    .select_from(jobs)
                    .where(jobs.c.tenant_id.in_(tenants), jobs.c.status == "RUNNING")
                )
                == 0
            )
        primary = Credential(*credential("bootstrap"))
        secondary = Credential(
            "f01_bootstrap", private_file("/run/secrets/postgres2_password", 4096).decode()
        )
        with session() as (store, _, _):
            for fixture in scope:
                tag, tenant = fixture["name"], UUID(fixture["tenant"])
                PHASE = tag + "/TARGET"
                target, names, refs = target_data(control, tenant)
                bootstrap = connection_engine(
                    target, names, primary if target.host == "postgres" else secondary
                )
                try:
                    with bootstrap.connect() as c:
                        before = fingerprint(c, list(build_metadata().tables.values()))
                        prior = c.scalar(
                            sa.text("SELECT version_num FROM public.alembic_version_tenant")
                        )
                        assert prior in ("f04_tenant_0003", VERSION)
                        assert not c.scalar(
                            sa.text("SELECT to_regclass('ops.f05_rollback_probe') IS NOT NULL")
                        )
                    save(tag + "-before.json", {"tenant": str(tenant), "f04_fingerprints": before})
                    for kind in ("app", "readonly"):
                        role_login(target, names, store.read(refs[kind]), kind)
                    if mode == "preflight":
                        print(
                            "PASS F05 PREFLIGHT "
                            + tag
                            + ": scope/TLS/roles/snapshot; no migration."
                        )
                        continue
                    PHASE = tag + "/DDL_FAIL"
                    seen = False

                    def failing(target, names, secret, repository):
                        nonlocal seen
                        with migration_session(target, names, secret) as c:
                            apply_spaces(c, names, repository)
                            c.exec_driver_sql("CREATE TABLE ops.f05_rollback_probe(x integer)")
                            try:
                                c.exec_driver_sql("SELECT 1/0")
                            except sa.exc.DBAPIError as error:
                                assert error.orig.sqlstate == "22012"
                                seen = True
                                raise

                    try:
                        migrate_controlled(
                            control,
                            tenant,
                            DAY_ACTOR,
                            store,
                            CA,
                            ROOT,
                            runner=failing,
                            profile="embeddings",
                        )
                    except MigrationError:
                        pass
                    else:
                        raise RuntimeError("DDL_FAILURE_ACCEPTED")
                    assert seen
                    with Session(control) as c:
                        row = c.get(Tenant, tenant)
                        assert (row.state, row.migration_state, row.observed_version) == (
                            "FAILED",
                            "MIGRATION_FAILED",
                            None,
                        )
                    with bootstrap.connect() as c:
                        assert (
                            c.scalar(
                                sa.text("SELECT version_num FROM public.alembic_version_tenant")
                            )
                            == prior
                        )
                        assert not c.scalar(
                            sa.text("SELECT to_regclass('ops.f05_rollback_probe') IS NOT NULL")
                        )
                        assert fingerprint(c, list(build_metadata().tables.values())) == before
                    PHASE = tag + "/RECOVER"
                    for _ in range(2):
                        assert (
                            migrate_spaces_controlled(control, tenant, DAY_ACTOR, store, CA, ROOT)
                            == VERSION
                        )
                    profile = qwen_profile()
                    space = uuid5(tenant, "F05/space/v1:" + profile.fingerprint())
                    PHASE = tag + "/REGISTER"
                    for _ in range(2):
                        with migration_session(target, names, store.read(refs["migrator"])) as c:
                            assert register_space(c, names, space, profile) == space
                    for kind in ("app", "readonly"):
                        role_login(target, names, store.read(refs[kind]), kind)
                    with bootstrap.connect() as c:
                        assert fingerprint(c, list(build_metadata().tables.values())) == before
                        assert (
                            c.scalar(sa.text("SELECT count(*) FROM knowledge." + table_name(space)))
                            == 0
                        )
                    resolved = CatalogResolver(control, profile="embeddings").resolve(
                        AdministrativeTenant(tenant)
                    )
                    assert resolved.host == target.host and resolved.database == names.database
                    for old_profile in ("identity", "documents", "ingestion"):
                        try:
                            CatalogResolver(control, profile=old_profile).resolve(
                                AdministrativeTenant(tenant)
                            )
                        except TenantAccessError as error:
                            assert error.code == "SCHEMA_INCOMPATIBLE"
                        else:
                            raise RuntimeError("OLD_PROFILE_ACCEPTED")
                    save(
                        tag + "-adopted.json",
                        {
                            "tenant": str(tenant),
                            "head": VERSION,
                            "space_id": str(space),
                            "profile_fingerprint": profile.fingerprint(),
                            "f04_fingerprints": before,
                        },
                    )
                    print(
                        "PASS F05 ADOPT "
                        + tag
                        + ": FAILED/rollback/recovery/repeat; space Qwen empty; F04 retained."
                    )
                finally:
                    bootstrap.dispose()
        with control.connect() as c:
            assert fingerprint(c, list(IdentityBase.metadata.tables.values())) == identities_before
            assert fingerprint(c, [jobs]) == jobs_before
        assert {key: value.hex() for key, value in snapshot(control).items()} == legacy_before
        save("summary-" + mode + ".json", {"mode": mode, "fixtures": 4, "legacy_retained": True})
        print(
            "PASS F05 " + mode.upper() + ": identities/jobs/other tenants retained; day preserved."
        )
    finally:
        control.dispose()


if __name__ == "__main__":
    logging.disable(logging.CRITICAL)
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("preflight", "adopt"))
    args = parser.parse_args()
    try:
        run(args.mode)
    except Exception as error:
        state = getattr(getattr(error, "orig", error), "sqlstate", None)
        code = (
            "SQLSTATE_" + state
            if isinstance(state, str) and re.fullmatch("[A-Z0-9]{5}", state)
            else "REFUSED"
        )
        print(
            "F05-ADOPT " + PHASE + " " + type(error).__name__ + " " + code + "; resources retained."
        )
        raise SystemExit(1) from None
