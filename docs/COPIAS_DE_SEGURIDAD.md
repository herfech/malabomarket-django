# Copias de seguridad

Hay que proteger dos cosas: **la base de datos** (anuncios, usuarios, cobros, recibos) y **las fotos** (el bucket).

## Base de datos
- **Render PostgreSQL** (planes de pago) hace copias diarias automáticas y permite restaurar a un momento concreto. Comprueba en el panel de la base de datos → *Recovery* que están activas.
- **Copia propia semanal** (recomendada, porque queda fuera de Render). Desde cualquier equipo con `pg_dump` instalado:
  ```
  DATABASE_URL="<External Database URL de Render>" ./scripts/backup_db.sh ./backups
  ```
  Genera `malabomarket-AAAAMMDD-HHMMSS.sql.gz` y conserva las 30 últimas. Guarda los archivos en un disco externo o en un bucket distinto del de las fotos.
- **Restaurar**:
  ```
  gunzip -c backups/malabomarket-XXXX.sql.gz | psql "$DATABASE_URL"
  ```
  Hazlo primero sobre una base de datos vacía de prueba para verificar que la copia funciona.

## Fotos
- Activa el **versionado** del bucket (R2/S3/B2) para poder recuperar fotos borradas por error.
- Opcional: sincroniza el bucket a otro con `rclone sync`.

## Qué no se pierde nunca
Los recibos no se borran ni se reutilizan sus números: si se anula uno, queda marcado como anulado con quién y por qué. El registro de auditoría solo se escribe desde el código.

## Prueba trimestral
Cada tres meses restaura la última copia en una base de datos de prueba y comprueba que se ven anuncios y recibos. Una copia que nunca se ha restaurado no es una copia.
