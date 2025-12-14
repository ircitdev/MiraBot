#!/bin/bash
#
# Автоматический бэкап базы данных MIRA BOT
# Использование: ./backup_db.sh [retention_days]
#

set -e

# Настройки
BACKUP_DIR="${BACKUP_DIR:-/backup/mira_bot}"
DB_PATH="${DB_PATH:-/root/mira_bot/mira_bot.db}"
RETENTION_DAYS="${1:-7}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/mira_bot_${TIMESTAMP}.db"
LOG_FILE="${BACKUP_DIR}/backup.log"

# Функция логирования
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Создаём директорию для бэкапов
mkdir -p "$BACKUP_DIR"

log "=== Starting backup ==="

# Проверяем наличие БД
if [ ! -f "$DB_PATH" ]; then
    log "ERROR: Database file not found: $DB_PATH"
    exit 1
fi

# Создаём бэкап
log "Creating backup: $BACKUP_FILE"
cp "$DB_PATH" "$BACKUP_FILE"

# Проверяем успешность
if [ -f "$BACKUP_FILE" ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "Backup created successfully: $BACKUP_FILE ($SIZE)"
else
    log "ERROR: Failed to create backup"
    exit 1
fi

# Сжимаем бэкап
log "Compressing backup..."
gzip "$BACKUP_FILE"
BACKUP_FILE="${BACKUP_FILE}.gz"

if [ -f "$BACKUP_FILE" ]; then
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log "Backup compressed: $BACKUP_FILE ($SIZE)"
fi

# Удаляем старые бэкапы
log "Removing backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -name "mira_bot_*.db.gz" -type f -mtime +$RETENTION_DAYS -delete

REMAINING=$(find "$BACKUP_DIR" -name "mira_bot_*.db.gz" -type f | wc -l)
log "Remaining backups: $REMAINING"

log "=== Backup completed ==="
