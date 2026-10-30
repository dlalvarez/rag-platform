# F00 — Ejecución en ragdev01

Código: `/home/diego/proyectos/rag-platform`, rama `feat/F00-bootstrap` desde develop.
Python del host: 3.12.3 (Ubuntu); contenedor/CI: 3.12.12; uv: 0.13.6.
No se crea un entorno de servicios en el equipo personal.

## Preparación

El responsable autorizó el acceso SSH y la implementación/pruebas de F00 en ragdev01.
Diego habilitó el grupo docker y creó el directorio raíz de datos. El grupo docker
tiene privilegios equivalentes a administración del host. No se configura sudo sin contraseña.

Herramientas aisladas del sistema:
```bash
python3 -m venv ~/.local/share/rag-f00-tools
~/.local/share/rag-f00-tools/bin/pip install uv==0.13.6
cd /home/diego/proyectos/rag-platform
~/.local/share/rag-f00-tools/bin/uv sync --locked --python /usr/bin/python3
.venv/bin/pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
python3 scripts/check_docs.py
.venv/bin/python scripts/f00_negative_checks.py
```

La instalación necesita red; después las pruebas unitarias bloquean conexiones de red.
No requieren Docker, API keys ni servicios. El lock fija dependencias transitivas y hashes.
La CI usa los mismos comandos sobre Python 3.12.12.

## Datos y servicios de ensayo

Una sola vez sobre directorio vacío:
```bash
python3 scripts/f00_prepare.py --host --data-root /srv/rag-data/rag-platform/f00
```

El script exige montaje ext4 real en /srv/rag-data, ruta sin enlaces simbólicos,
al menos 5 GiB libres y directorio vacío. Genera secretos efímeros fuera de Git y un
.env excluido con rutas/UID/GID; no imprime credenciales. No usar datos reales.
El API no recibe secretos de PostgreSQL ni S3.

```bash
python3 scripts/f00_compose.py config --quiet
python3 scripts/f00_compose.py build minio api smoke
python3 scripts/f00_compose.py up -d --wait --wait-timeout 180 postgres minio api
python3 scripts/f00_compose.py run --rm --no-deps smoke
python3 scripts/f00_compose.py ps
```

Usar el wrapper en el host: vuelve a verificar el montaje antes de cada operación.
Compose también impide crear automáticamente directorios bind inexistentes.
PostgreSQL y MinIO no publican puertos al host. API solo en 127.0.0.1:8000; para
consultarla remotamente usar túnel SSH. No exponerla a Internet. /healthz es liveness
del placeholder, no readiness conjunta de PostgreSQL/S3.

El total configurado para los tres servicios es 1.75 CPU y 4.5 GiB; smoke añade
0.25 CPU y 512 MiB mientras dura. La compilación de MinIO usa dos procesos Go;
estos límites de runtime no limitan Docker BuildKit. Supervisar memoria/disco
antes de repetir builds en la VM de 2 vCPU/16 GiB.

## MinIO y versiones

Se conserva MinIO; no se cambia de proveedor. Las consultas de manifiestos oficiales
fallaron (Docker Hub: acceso denegado; Quay: 401), por lo que se compila la release
oficial RELEASE.2025-10-15T17-29-55Z con Go 1.24.9 y go.sum/sumdb, siguiendo la
[instrucción upstream](https://github.com/minio/minio/releases/tag/RELEASE.2025-10-15T17-29-55Z).
Go, Python y PostgreSQL/pgvector tienen imágenes base fijadas por digest.
Esto fija insumos, sin prometer builds bit a bit.

MinIO upstream está [archivado](https://github.com/minio/minio). Esta receta es solo
para desarrollo sintético F00; no acredita mantenimiento, revisión de CVEs ni aptitud
para producción. La revisión de almacenamiento para fases posteriores debe registrar
este riesgo, sin sustituir MinIO unilateralmente. No se aprueba ADR-0004 por este trabajo.

PostgreSQL 17 + pgvector 0.8.7: imagen oficial pgvector 0.8.7-pg17-bookworm.
FastAPI/uvicorn y las herramientas exactas constan en pyproject.toml y uv.lock.
No hay migraciones, rag_control, tenants ni endpoints de negocio.

## Fallos y rollback

Con el stack saludable, detener minio, ejecutar smoke (debe fallar con salida 1,
sin credenciales/traceback), reiniciar minio, esperar salud y repetir smoke.
Si falta configuración, Docker Compose debe rechazarla antes de iniciar servicios.
No mostrar docker compose config sin --quiet: puede revelar datos operativos.

Para detener solo este proyecto:
```bash
python3 scripts/f00_compose.py down
```

Down conserva los directorios de datos y credenciales. No usar down -v, prune,
rm masivo ni tocar /srv/rag-data/docker o containerd. Revertir código mediante PR.
Si un build falla, revisar solo el error saneado, corregir y repetir. Un fallo de salud
o smoke impide declarar AC-F00-02 completado. Snapshot VMM no sustituye backup externo.

Recrear credenciales requiere detener F00 y planificar recreación de sus datos
sintéticos; no sobrescribir claves con PostgreSQL ya inicializado. Para persistencia,
repetir down/up sin borrar directorios y verificar una fixture sintética conservada.
