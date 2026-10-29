# ADR 0002 — Infraestructura inicial de desarrollo en Synology VMM

- **Estado:** entorno implementado y observado; ADR ratificado documentalmente en F00 (PR #2).
- **Fecha:** 2026-10-28.

## Decisión
Desarrollo/integración en Synology DS923+ (32 GB de RAM), sobre VM `rag-dev-01` con Ubuntu Server 24.04.5 LTS, 2 vCPU, 16 GB RAM, disco del SO 40 GiB y disco adicional ext4 de 120 GiB. Hostname de Ubuntu `ragdev01`; red privada local. `/srv/rag-data` en SSD/NVMe independiente. Docker Engine, Compose y containerd ejecutan servicios de aplicación en contenedores.

## Evidencia observada
Tras reinicio: `findmnt /srv/rag-data` en `/dev/sdb1`, servicios Docker y containerd activos, directorios `/srv/rag-data/docker` y `/srv/rag-data/containerd`, y `docker run --rm hello-world` exitoso. SSH mediante Ed25519 probado; se mantiene contraseña de SSH por decisión operativa actual. Snapshot local VMM creado.

## Riesgos y límites
Pool SSD de tipo Basic con **un solo disco y sin redundancia**. Snapshot local no es backup independiente. El procesador NAS es limitado para embeddings locales/cargas de ingesta simultáneas. No usar este entorno como producción con SLA. Documentar respaldos externos y pruebas de restauración antes de datos importantes.

## Portabilidad
Docker Compose, scripts de despliegue y aplicación no deben requerir APIs Synology. El acceso a directorios persistentes será configurable; versiones de imágenes se fijarán al implementar servicios.

## Pendiente
Confirmar cobertura del snapshot sobre ambos discos; diseñar backup externo, límites de recursos, firewall, redes Compose y perfiles de despliegue.
