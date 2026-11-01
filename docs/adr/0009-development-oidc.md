# ADR 0009 — IdP OIDC de desarrollo para F02

Estado: propuesta para resolver D-04; no aplicada.
[Registro D-04](../13-decisions-risks.md), [arquitectura](../02-architecture.md),
[plan F02](../../specs/F02-identidad-membresias/plan.md).

## Decisión propuesta

Usar Keycloak únicamente como IdP local de pruebas en ragdev01. La arquitectura
ya lo contempla como opción. La aplicación conserva proveedor configurable por
issuer/audience/JWKS; no SDK administrativo del IdP dentro de la lógica de negocio.
Producción y proveedor comercial quedan sin decidir.

Contenedor fijado por versión/digest después de verificar release y avisos.
TLS validado, issuer estable y PostgreSQL propio; no exponer administración a LAN
o Internet. Bootstrap de fixture sintética separado de validación de tokens.
No IdP pagado, usuarios reales ni contraseñas locales del producto.

## Motivo y alternativas

Permite probar autenticación y rotación reales sin contratar servicio externo.
Añade mantenimiento y consumo de memoria/CPU a la VM de 2 vCPU/16 GiB;
el presupuesto y la prueba real son condición de T001, no capacidad presumida.

Usar un IdP externo ya disponible evitaría operarlo, pero no se ha identificado
una cuenta/servicio autorizado para este proyecto. No crearla unilateralmente.
Un emisor simulado sirve para unit tests, pero no satisface integración con IdP real.
Un proveedor OIDC local más pequeño requeriría comparar compatibilidad y operación;
no se introduce solo por preferencia del implementador.

## Seguridad y reversión

Ningún rol de producto o membresía se concede porque un JWT diga ser admin/tenant.
La identidad global usa issuer+sub; no email. Access token para audiencia API,
firma y tiempos validados; ID token no habilita acceso a la API.
Secretos fuera de Git, argumentos y logs; OpenBao de infraestructura sigue separado.

Retirar perfil IdP de desarrollo y cambiar configuración del adaptador con pruebas
de contrato; no prometer migración automática de identidades entre emisores.
Cambiar issuer requiere mapeo explícito revisado; no fusionar sujetos por email.
Conservar bases/fixtures y F00/F01. No borrar datos como parte de reversión.

## Decisión pendiente y autoridad

D-04 está expresamente abierta en docs/13. Constitución P10 reserva arquitectura
al humano y ADR-0007 mantiene decisión expresa para arquitectura/contratos.
La delegación de revisión ordinaria no se registra como ratificación ficticia
del proveedor. Esta propuesta deja listo el cambio concreto para esa única decisión.
Tras resolverla, no pedir confirmación por cada tarea, prueba o PR dentro de F02.

## Fuentes consultadas

[Contenedores Keycloak](https://www.keycloak.org/server/containers),
[configuración y TLS](https://www.keycloak.org/server/configuration-production),
[OpenID Connect Core](https://openid.net/specs/openid-connect-core-1_0.html),
[validación JWT](https://pyjwt.readthedocs.io/en/latest/api.html).
Consulta del 2026-10-31. La documentación no demuestra funcionamiento en ragdev01.
Versiones/digest y compatibilidad se fijan en T001 antes de ejecutar el IdP.
