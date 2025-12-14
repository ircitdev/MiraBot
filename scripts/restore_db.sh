#!/bin/bash
#
# Восстановление базы данных из бэкапа
# Использование: ./restore_db.sh <backup_file>
#

set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file>"
    echo "Example: $0 /backup/mira_bot/mira_bot_20241214_120000.db.gz"
    exit 1
fi

BACKUP_FILE="$1"
DB_PATH="${DB_PATH:-/root/mira_bot/mira_bot.db}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Проверяем файл бэкапа
if [ ! -f "$BACKUP_FILE" ]; then
    log "ERROR: Backup file not found: $BACKUP_FILE"
    exit 1
fi

log "=== Starting restore ==="
log "Backup file: $BACKUP_FILE"
log "Target DB: $DB_PATH"

# Останавливаем бота
log "Stopping bot..."
systemctl stop mirabot || true

# Создаём резервную копию текущей БД
if [ -f "$DB_PATH" ]; then
    SAFETY_BACKUP="${DB_PATH}.before_restore_${TIMESTAMP}"
    log "Creating safety backup: $SAFETY_BACKUP"
    cp "$DB_PATH" "$SAFETY_BACKUP"
fi

# Распаковываем и восстанавливаем
log "Restoring database..."
if [[ "$BACKUP_FILE" == *.gz ]]; then
    gunzip -c "$BACKUP_FILE" > "$DB_PATH"
else
    cp "$BACKUP_FILE" "$DB_PATH"
fi

# Проверяем целостность
log "Checking database integrity..."
sqlite3 "$DB_PATH" "PRAGMA integrity_check;" || {
    log "ERROR: Database integrity check failed"
    if [ -f "$SAFETY_BACKUP" ]; then
        log "Restoring safety backup..."
        cp "$SAFETY_BACKUP" "$DB_PATH"
    fi
    exit 1
}

# Запускаем бота
log "Starting bot..."
systemctl start mirabot

log "=== Restore completed ==="
log "Safety backup saved as: $SAFETY_BACKUP"
