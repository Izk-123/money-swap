#!/bin/bash
set -e

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/moneyswap"
BACKUP_FILE="$BACKUP_DIR/db_backup_$DATE.sql"

mkdir -p $BACKUP_DIR

# PostgreSQL backup
pg_dump -h $DB_HOST -U $DB_USER $DB_NAME > $BACKUP_FILE

# Compress backup
gzip $BACKUP_FILE

# Keep only last 7 backups
ls -t $BACKUP_DIR/db_backup_*.sql.gz | tail -n +8 | xargs rm -f

echo "✅ Database backup created: $BACKUP_FILE.gz"
