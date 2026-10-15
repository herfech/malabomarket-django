#!/usr/bin/env bash
# Copia de seguridad de la base de datos en un archivo comprimido.
# Uso:  DATABASE_URL=postgres://... ./scripts/backup_db.sh [carpeta_destino]
set -euo pipefail
DEST="${1:-./backups}"
mkdir -p "$DEST"
FILE="$DEST/malabomarket-$(date +%Y%m%d-%H%M%S).sql.gz"
pg_dump --no-owner --no-privileges "$DATABASE_URL" | gzip > "$FILE"
echo "Copia creada: $FILE"
# Conserva solo las 30 más recientes
ls -1t "$DEST"/malabomarket-*.sql.gz | tail -n +31 | xargs -r rm --
