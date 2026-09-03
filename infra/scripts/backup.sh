#!/bin/bash
set -e

BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="smartfeed"
DB_USER="smartfeed"
DB_HOST="postgres"

mkdir -p $BACKUP_DIR

echo "Backing up PostgreSQL..."
pg_dump -h $DB_HOST -U $DB_USER $DB_NAME | gzip > $BACKUP_DIR/${DB_NAME}_${TIMESTAMP}.sql.gz

echo "Backing up Redis..."
redis-cli -h redis SAVE
cp /data/dump.rdb $BACKUP_DIR/redis_${TIMESTAMP}.rdb

echo "Cleaning old backups (older than 30 days)..."
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete
find $BACKUP_DIR -name "*.rdb" -mtime +30 -delete

echo "Backup complete: ${BACKUP_DIR}/${DB_NAME}_${TIMESTAMP}.sql.gz"
