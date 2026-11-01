# F02 — IdP de desarrollo, T001

Keycloak solo desarrollo aprobado por Diego en ADR-0009/PR #19.
No IdP de producción, usuarios reales ni UI de producto.

## Operación en ragdev01

Trabajar en /home/diego/proyectos/rag-platform. Preparación inicial:
    python3 scripts/f02_host.py prepare
    python3 scripts/f02_host.py config
    python3 scripts/f02_host.py build
    python3 scripts/f02_host.py up
    python3 scripts/f02_host.py check
    python3 scripts/f02_host.py status

prepare no sobrescribe datos ni configuración existentes. Si falla o hay estado
parcial, conservarlo y revisar; no borrar/reinicializar para ocultar el fallo.
No repetir prepare en el entorno existente.

Datos: /srv/rag-data/rag-platform/f02, ext4 montado. .env.f02 contiene solo rutas/UID.
Archivos TLS y bootstrap privados; certificados públicos 0444, secretos 0600,
directorios 0700. No mostrar config/keycloak.conf o config/init.sql:
contienen la contraseña SQL del IdP. No montarlos en API/herramienta de comprobación.
La clave de la CA no se monta en ningún servicio.

IdP: Keycloak 26.8.1, índice OCI
sha256:3f3c5f8e03c614774b4bd9173b88391fefa4153bfc010d8012d59ad825377332.
Imagen local optimizada rag-f02-keycloak:26.8.1; registrar image ID real en evidencia.
PostgreSQL: imagen PG17/pgvector 0.8.7 ya fijada en F01, sin actualizar sus clústeres.
Esta base no instala esquemas RAG ni usa el rol bootstrap como runtime:
f02_idp es NOSUPERUSER/NOCREATEDB/NOCREATEROLE/NOREPLICATION/NOBYPASSRLS.

TLS API IdP y JDBC verify-full con CA propia; http deshabilitado.
Issuer interno fijo: https://idp:8443/realms/rag-dev. Realm no permite registro,
reset de password o login por email. Importación inicial sin usuarios ni clientes.
T001 no crea administrador inicial; la preparación de identidades/cliente sintéticos
para T002/T006 será una operación separada, con bootstrap privado y auditado.
Nunca pasar credenciales a argumentos ni copiar la sesión diaria de OpenBao al IdP.

Red Docker interna rag-f02-dev_f02; sin puertos publicados. El check solo recibe CA
y su script, sin claves privadas, contraseñas de SQL, Docker socket o credenciales Bao.
No acceso a F00/F01 desde esta red. No exponer hostname/puertos a LAN automáticamente.

## Presupuesto y aceptación

Límites: IdP 1536 MiB/0.75 CPU, PG 512 MiB/0.25 CPU y check serial 768 MiB/0.25 CPU.
API F02 aún no creada. Medir consumo/OOM/readiness real, no inferir capacidad del límite.
La comprobación espera hasta 180 segundos y valida discovery/JWKS reales;
una conexión sin la CA privada debe fallar por verificación de certificado.

T001 no prueba emisión ni validación de access tokens, login de usuario, rotación,
membresías, roles, API o autorización tenant. Esos AC siguen abiertos.
Pruebas unitarias/CI offline no requieren Keycloak ni Internet.
La integración real se ejecuta aparte solo en ragdev01.

## Conservación y reversión

No down -v, prune, eliminación de bases o buckets ni reinicio de Bao/F00/F01.
Retirar tráfico y detener únicamente servicios propios F02 si fuera necesario,
conservando /srv/rag-data/rag-platform/f02 y sus secretos. No prometer backup/restore.
El wrapper no ofrece borrado. Cambios de hostname/issuer o sustitución de IdP
requieren compatibilidad/mapeo explícitos; no vincular identidades por email.

Fuentes verificadas:
[release 26.8.1](https://github.com/keycloak/keycloak/releases/tag/26.8.1),
[contenedores](https://www.keycloak.org/server/containers),
[TLS/configuración](https://www.keycloak.org/server/configuration-production).
La release incorpora correcciones de seguridad; no equivale a un escaneo completo
de la imagen ni garantiza ausencia de vulnerabilidades. Sin federation, broker,
token exchange o extensiones custom de IdP en este perfil.
