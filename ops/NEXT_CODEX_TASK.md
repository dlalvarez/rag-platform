# Siguiente tarea Codex — sesión diaria acreditada

La configuración de ADR-0008 está aplicada y verificada en ragdev01. Diego completó
CONFIGURAR24H: root temporal y ensayo revocados, configuración original restaurada.
daily verify y daily-cli pasaron en procesos independientes, sin nueva contraseña.
La sesión operativa vence el 2026-11-01T21:34:19-05:00 (Bogotá).
Conservar ese vencimiento; no revocar al terminar cada batería ni iniciar otro día.

Consultar status antes de pruebas autorizadas:
    python3 scripts/f01_host.py run --rm -T daily status

No repetir configure, reiniciar OpenBao ni regenerar root para trabajo ordinario.
Al vencer, el operador puede iniciar otro día una sola vez con daily start;
no pedir contraseña, unseal o tokens en chat. Manual: [DAY_ACCESS](f01/DAY_ACCESS.md).

Toda ejecución, desarrollo y pruebas en ragdev01. Conservar datos, F00, rol corto
y clon T007. La autorización diaria habilita pruebas dentro del alcance acordado;
no autoriza una fase nueva. F01 sigue cerrada. El siguiente paso funcional requiere
definir y ratificar F02 conforme al roadmap antes de implementarla.
No promover main ni crear tags con esta mejora.
