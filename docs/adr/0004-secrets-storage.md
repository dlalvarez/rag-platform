# ADR 0004 — Separación de secretos y almacenamiento de objetos

**Estado:** propuesto para ratificación F01; ampliado el 2026-10-30.
El responsable eligió incluir OpenBao en la propuesta. No está instalado ni aprobado
por este documento. Referencias: [plan F01](../../specs/F01-aislamiento-provisionamiento/plan.md)
y [decisiones de ratificación](../../specs/F01-aislamiento-provisionamiento/ratification.md).

## Decisión propuesta

Credenciales propias por tenant en un secret manager; rag_control conserva únicamente
referencias opacas y versiones no secretas. Bucket privado y principal/política propia
por tenant. Prohibido almacenar passwords, tokens, documentos o prompts en control/Git.

Para desarrollo F01: OpenBao 2.7.2, imagen oficial
ghcr.io/openbao/openbao:2.7.2@sha256:5046911075e137e154ce49ab051502f4ec7cf367d484ae4a4dce665d9b90561f.
Manifiesto consultado desde ragdev01; sin descargar capas, arrancar servicio ni
crear credenciales. Verificar de nuevo compatibilidad/avisos de seguridad antes de
implementarlo, sin tratar esa consulta como prueba del servicio.

Un nodo con almacenamiento Raft persistente bajo /srv/rag-data/rag-platform/f01,
KV v2, TLS validado y políticas por finalidad. No server -dev, no raíz administrativa
como identidad de aplicación, no acceso anónimo ni puerto expuesto a LAN/Internet.
Raft de un nodo no ofrece HA ni protección frente a pérdida del SSD/NAS.
Se prefiere Raft a filesystem no transaccional; frente a backend PostgreSQL evita
acoplar la recuperación del almacén de secretos a las instancias que aprovisiona.

Bootstrap por Diego en terminal segura: inicializar, custodiar unseal fuera del host,
crear identidad de operador de infraestructura y AppRole para la CLI. Propuesta solo
dev: Shamir 1 de 1, acorde con un único operador y datos sintéticos. La ubicación de
custodia y copia protegida se confirman antes de inicializar; no se generan claves
hasta entonces. No conservar unseal en el contenedor, Git, chat, logs ni junto a Raft.
Cada reinicio requiere desbloqueo manual. Root token inicial se revoca tras configurar
políticas y comprobar acceso/revocación; no queda como credencial de runtime.

Autenticación administrativa propuesta: userpass de OpenBao para el operador, con
password introducida por Diego y guardada fuera del host en un almacén protegido.
Es autenticación de infraestructura del secret manager, no identidad SaaS de F02.
Política del operador limitada al namespace F01 y a emitir SecretID de su AppRole,
sin administración general del host ni root permanente de OpenBao.
AppRole exige SecretID; propuesta de TTL SecretID 10 min/1 uso, token 15 min,
max TTL 60 min, con renovación acotada y reautenticación si caduca.
SecretID y token se entregan por canal protegido/archivos temporales 0600 o tmpfs,
nunca argumentos de shell. Probes comprueban sellado, expiración, denegación y
ausencia de secretos en excepciones/logs; no se ocultan valores solo con un repr bonito.

SecretStore abstrae lectura/escritura por ref y versión, operaciones CAS idempotentes
y fallos saneados. No almacenar DSN con password en catálogo. Credenciales
administrativas SQL/MinIO, migrator y app separadas. El provisionador puede gestionar
el namespace F01 completo por su función administrativa; eso no se atribuye a
principales de tenant. Los permisos de datos se verifican con sus credenciales reales,
sin usar root en pruebas que pretenden demostrar aislamiento.

## Alternativas y límites

Archivos protegidos o secretos Compose siguen siendo útiles para bootstrap/TLS,
pero no sustituyen el secret manager de credenciales tenant propuesto aquí.
Un servicio externo administrado exigiría una cuenta/proveedor y conectividad no
acordados para desarrollo; no se introduce en esta fase.
La decisión de producción incluye disponibilidad, custodia, rotación, backups y
recuperación, y requiere aprobación posterior; no se presume satisfecha con este perfil.

MinIO se conserva con la receta de F00. Su upstream archivado y el binario compilado
son riesgos de mantenimiento ya documentados. No se cambia proveedor en esta propuesta.
Antes de usar datos relevantes o promover ambientes, revisar soporte, seguridad y
recuperación; F01 solo admite fixtures sintéticas.

## Validación requerida

V03: refs opacas, restart sellado y posterior desbloqueo, lectura de secretos conservada,
tokens inválidos/caducados/denegados sin fallback ni filtración.
V04: get/put/list propios y get/put/list cruzados A↔B denegados; objetos anónimos
rechazados. Los permisos solo se consideran probados con integración real.
No copiar credenciales ni respuestas de inicialización a evidence.

## Operación y reversión

Detener el proyecto conserva Raft y sus datos. No desactivar TLS, exportar secretos
a .env ni cambiar backend automáticamente si OpenBao falla. Recuperación o cambio
de proveedor: propuesta explícita, inventario de refs y procedimiento probado;
sin datos importantes no se afirma backup externo/restore ni RPO/RTO.

Fuentes consultadas el 2026-10-30:
[release 2.7.2](https://github.com/openbao/openbao/releases/tag/v2.7.2),
[instalación oficial](https://openbao.org/docs/install/),
[Raft](https://openbao.org/docs/configuration/storage/raft/),
[seal/unseal](https://openbao.org/docs/concepts/seal/),
[AppRole](https://openbao.org/docs/auth/approle/),
[KV v2](https://openbao.org/docs/secrets/kv/kv-v2/).
