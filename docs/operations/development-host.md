# Runbook — Host de desarrollo

**Host:** VM `rag-dev-01` / Ubuntu `ragdev01` en Synology VMM. **IP LAN observada:** `192.168.78.161`; puede cambiar hasta configurar reserva DHCP. No exponer a Internet.

## Comprobaciones de solo lectura
```bash
hostnamectl
systemctl is-active docker containerd ssh
findmnt /srv/rag-data
df -hT / /srv/rag-data
sudo docker info --format '{{.DockerRootDir}}'
sudo containerd config dump | grep '^root ='
systemctl --failed
```

## Layout
- Sistema Ubuntu: disco 40 GiB, partición raíz ext4.
- Datos: 120 GiB ext4, UUID `0d57c5d6-173c-47e2-8650-62d69dc055f2`, montado en `/srv/rag-data`.
- Docker data-root: `/srv/rag-data/docker`.
- containerd root: `/srv/rag-data/containerd`.
- Unidades Docker/containerd con dependencia `RequiresMountsFor=/srv/rag-data`.

## Acceso y límites
SSH con llave validada desde macOS; contraseña SSH sigue habilitada por compatibilidad con clientes Devolutions RDM y Warp. No guardar llaves ni contraseñas en GitHub. Usar `sudo` para Docker (no añadir usuarios indiscriminadamente al grupo docker).

## Mantenimiento pendiente
`containerd` muestra advertencia de configuración `version=2` interpretada por una versión más reciente. No migrar sin copia y ventana de validación. Confirmar backups independientes del NAS.

## No hacer
No publicar PostgreSQL/Redis a Internet, no escribir datos de aplicación en el disco de Ubuntu, no desplegar servicios sin spec aprobada, no presentar snapshot como recuperación verificada.
