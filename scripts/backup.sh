#!/bin/sh
# Local backup of El Orientador: database dump + stored PDFs + checksum manifest. No cloud involved.
#   backup.sh create            new backup under $BACKUP_DIR/<timestamp>, keeps the newest $BACKUP_KEEP
#   backup.sh verify [dir]      checks the checksums and that the dump is readable (default: newest)
#   backup.sh restore <dir> --yes   replaces the database and the stored PDFs with that backup
# Env: DATABASE_URL (required), STORAGE_DIR (/app/storage), BACKUP_DIR (/backups), BACKUP_KEEP (14)
set -eu

STORAGE_DIR="${STORAGE_DIR:-/app/storage}"
BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_KEEP="${BACKUP_KEEP:-14}"
: "${DATABASE_URL:?DATABASE_URL is required}"

newest() { ls -1d "$BACKUP_DIR"/*/ 2>/dev/null | sort | tail -n 1 | sed 's:/$::'; }

do_verify() {
  dir="$1"
  [ -f "$dir/db.dump" ] && [ -f "$dir/manifest.sha256" ] || { echo "backup incompleto: $dir" >&2; return 1; }
  (cd "$dir" && sha256sum -c db.dump.sha256 >/dev/null) || { echo "dump corrompido" >&2; return 1; }
  pg_restore --list "$dir/db.dump" >/dev/null || { echo "dump ilegível" >&2; return 1; }
  if [ -s "$dir/manifest.sha256" ]; then
    (cd "$dir/storage" && sha256sum -c ../manifest.sha256 >/dev/null) || { echo "PDF corrompido ou ausente" >&2; return 1; }
  fi
  echo "ok: $dir"
}

case "${1:-}" in
  create)
    dir="$BACKUP_DIR/$(date -u +%Y%m%d-%H%M%S)"
    mkdir -p "$dir/storage"
    pg_dump --format=custom --no-owner "$DATABASE_URL" > "$dir/db.dump"
    (cd "$dir" && sha256sum db.dump > db.dump.sha256)
    if [ -d "$STORAGE_DIR" ]; then
      cp -a "$STORAGE_DIR"/. "$dir/storage"/
      find "$dir/storage" -name '.tmp-*' -type f -delete
    fi
    (cd "$dir/storage" && find . -type f -exec sha256sum {} +) > "$dir/manifest.sha256"
    do_verify "$dir"
    ls -1d "$BACKUP_DIR"/*/ | sort | head -n -"$BACKUP_KEEP" 2>/dev/null | while read -r old; do rm -rf "$old"; done
    ;;
  verify)
    do_verify "${2:-$(newest)}"
    ;;
  restore)
    dir="${2:?informe a pasta do backup}"
    [ "${3:-}" = "--yes" ] || { echo "restore substitui o banco e os PDFs atuais; repita com --yes" >&2; exit 2; }
    do_verify "$dir"
    pg_restore --clean --if-exists --no-owner --dbname="$DATABASE_URL" "$dir/db.dump"
    mkdir -p "$STORAGE_DIR"
    find "$STORAGE_DIR" -mindepth 1 -delete
    cp -a "$dir/storage"/. "$STORAGE_DIR"/
    echo "restaurado de $dir"
    ;;
  *)
    echo "uso: backup.sh create | verify [dir] | restore <dir> --yes" >&2
    exit 2
    ;;
esac
