# Pista tenant

T001 fija el contrato interno en `src/rag_platform/tenancy/contracts.py`.
La revisión Alembic tenant, vector y locks se implementan en T002/T006; esta carpeta
no acredita migración ni aislamiento de ninguna base tenant. No crear tablas de negocio.
