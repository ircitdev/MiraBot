#!/bin/bash
#
# Настройка cron для автоматических бэкапов
# Запускать от root на сервере
#

CRON_SCHEDULE="${1:-0 3 * * *}"  # По умолчанию в 3:00 каждый день
SCRIPT_PATH="/root/mira_bot/scripts/backup_db.sh"
RETENTION_DAYS="${2:-7}"

echo "Setting up cron job for database backups..."
echo "Schedule: $CRON_SCHEDULE"
echo "Retention: $RETENTION_DAYS days"

# Добавляем задачу в cron
(crontab -l 2>/dev/null | grep -v "$SCRIPT_PATH"; echo "$CRON_SCHEDULE $SCRIPT_PATH $RETENTION_DAYS >> /var/log/mira_backup.log 2>&1") | crontab -

echo "Cron job added successfully!"
echo ""
echo "Current crontab:"
crontab -l

echo ""
echo "To view backup logs: tail -f /var/log/mira_backup.log"
