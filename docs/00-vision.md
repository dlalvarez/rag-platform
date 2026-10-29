# 00 — Visión del producto y límites

## Problema

La información especializada se encuentra dispersa en manuales, procedimientos y documentos empresariales. Las búsquedas por palabras no siempre capturan el significado; los LLM sin recuperación pueden inventar datos y mezclar información sin autorización.

## Propuesta de valor

Una plataforma SaaS que permita crear repositorios de conocimiento, configurar asistentes y conversar con fuentes autorizadas, con trazabilidad documental, actualización incremental y aislamiento empresarial desde el primer día.

## Personas y espacios

- **Persona individual:** administra un tenant personal con varios repositorios.
- **Colaborador:** pertenece a uno o varios tenants organizacionales y conserva su tenant personal separado.
- **Administrador de tenant:** gestiona repositorios, asistentes, integrantes, roles y límites dentro de su organización.
- **Operador de plataforma:** aprovisiona y observa servicios globales sin acceder por defecto al contenido del cliente.

## Casos de uso iniciales

1. Cargar manuales Oracle/PostgreSQL/AWS y preguntar con citas de documento, página/sección y fragmento.
2. Mantener repositorios independientes en un tenant y crear asistentes con alcance explícito.
3. Demostrar que dos tenants no pueden acceder a documentos, conversaciones, índices ni objetos ajenos.
4. Sustituir un documento por nueva versión sin ofrecer respuestas con un índice a medio construir.
5. Registrar costos, consumo y errores por tenant sin centralizar contenido confidencial.

## Metas del MVP

Crear tenant personal y tenant empresarial de prueba; autenticación; autorización; dos repositorios independientes; documentos PDF texto, Markdown, TXT y DOCX; procesamiento asíncrono; indexación pgvector; búsqueda híbrida básica; respuestas con citas y abstención; UI mínima de administración y chat; pruebas automáticas de aislamiento; métricas y auditoría mínimas.

## Fuera del MVP

Facturación real, alta pública autoservicio, marketplace de asistentes, OCR intensivo, fine-tuning, búsqueda web autónoma, herramientas que ejecuten acciones externas, integraciones con agendas, cross-tenant knowledge sharing, móviles nativos, multi-región activo-activo, SLA contractuales y orquestación avanzada de agentes.

## Principio económico

Arquitectura SaaS-ready no significa operar todo el SaaS desde el primer día: el modelo de datos y la seguridad son fundacionales; el crecimiento comercial se agrega progresivamente.
