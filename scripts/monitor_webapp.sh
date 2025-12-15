#!/bin/bash
#
# Мониторинг WebApp для Mira Bot
# Проверяет доступность и автоматически перезапускает при проблемах
#

WEBAPP_URL="http://127.0.0.1:8081/"
SERVICE_NAME="mirabot-webapp"
LOG_FILE="/var/log/mira_webapp_monitor.log"
MAX_RETRIES=3
RETRY_DELAY=5

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

check_webapp() {
    # Проверяем HTTP ответ
    HTTP_CODE=$(curl -s -o /dev/null -w '%{http_code}' --connect-timeout 5 --max-time 10 "$WEBAPP_URL" 2>/dev/null)

    if [ "$HTTP_CODE" == "200" ]; then
        return 0
    else
        log "WARNING: WebApp returned HTTP $HTTP_CODE (expected 200)"
        return 1
    fi
}

check_process() {
    # Проверяем что процесс запущен
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        return 0
    else
        log "ERROR: Service $SERVICE_NAME is not active"
        return 1
    fi
}

restart_service() {
    log "Attempting to restart $SERVICE_NAME..."
    systemctl restart "$SERVICE_NAME"
    sleep 3

    if systemctl is-active --quiet "$SERVICE_NAME"; then
        log "SUCCESS: Service $SERVICE_NAME restarted successfully"
        return 0
    else
        log "ERROR: Failed to restart $SERVICE_NAME"
        return 1
    fi
}

# Main monitoring loop
main() {
    log "Starting WebApp monitor"

    # Проверяем процесс
    if ! check_process; then
        log "Service not running, attempting restart..."
        restart_service
        exit $?
    fi

    # Проверяем доступность с retry
    RETRY_COUNT=0
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        if check_webapp; then
            log "OK: WebApp is responding normally"
            exit 0
        fi

        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            log "Retry $RETRY_COUNT/$MAX_RETRIES in ${RETRY_DELAY}s..."
            sleep $RETRY_DELAY
        fi
    done

    # Все retry исчерпаны, перезапускаем
    log "CRITICAL: WebApp not responding after $MAX_RETRIES attempts"
    restart_service

    # Финальная проверка
    sleep 5
    if check_webapp; then
        log "SUCCESS: WebApp recovered after restart"
        exit 0
    else
        log "CRITICAL: WebApp still not responding after restart!"
        exit 1
    fi
}

main
