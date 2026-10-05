#!/bin/sh
set -eu

dataset="${BACKUP_DATASET}"
archive_dir="/backups/${dataset}"
metric_file="/backup-metrics/${dataset}.prom"
mkdir -p "${archive_dir}" /backup-metrics

read_stamp() {
    stamp_file="/backups/${dataset}-$1.stamp"
    if [ -f "${stamp_file}" ]; then sed -n '1p' "${stamp_file}"; else printf '0'; fi
}

write_stamp() {
    printf '%s\n' "$2" > "/backups/${dataset}-$1.stamp.tmp"
    mv "/backups/${dataset}-$1.stamp.tmp" "/backups/${dataset}-$1.stamp"
}

publish_metrics() {
    success="$(read_stamp success)"
    restore="$(read_stamp restore)"
    failure="$(read_stamp failure)"
    {
        printf '# TYPE newspulse_backup_last_success_timestamp_seconds gauge\n'
        printf 'newspulse_backup_last_success_timestamp_seconds{dataset="%s"} %s\n' "${dataset}" "${success}"
        printf '# TYPE newspulse_backup_last_restore_test_timestamp_seconds gauge\n'
        printf 'newspulse_backup_last_restore_test_timestamp_seconds{dataset="%s"} %s\n' "${dataset}" "${restore}"
        printf '# TYPE newspulse_backup_last_failure_timestamp_seconds gauge\n'
        printf 'newspulse_backup_last_failure_timestamp_seconds{dataset="%s"} %s\n' "${dataset}" "${failure}"
    } > "${metric_file}.tmp"
    mv "${metric_file}.tmp" "${metric_file}"
}

restore_test() {
    probe_db="${BACKUP_MONGO_DB}_restore_probe_$(date -u +%s)_$$"
    if ! mongorestore --uri="${BACKUP_MONGO_URI}" --archive="$1" --gzip \
        --nsFrom="${BACKUP_MONGO_DB}.*" --nsTo="${probe_db}.*"; then
        mongosh "${BACKUP_MONGO_URI}" --quiet --eval "db.getSiblingDB('${probe_db}').dropDatabase()" >/dev/null || true
        return 1
    fi
    collection_count="$(mongosh "${BACKUP_MONGO_URI}" --quiet --eval "db.getSiblingDB('${probe_db}').getCollectionNames().length")"
    mongosh "${BACKUP_MONGO_URI}" --quiet --eval "db.getSiblingDB('${probe_db}').dropDatabase()" >/dev/null
    [ "${collection_count}" -gt 0 ]
}

publish_metrics
while :; do
    now="$(date -u +%s)"
    archive="${archive_dir}/${dataset}-${now}.archive.gz"
    if mongodump --uri="${BACKUP_MONGO_URI}" --db="${BACKUP_MONGO_DB}" \
        --archive="${archive}.tmp" --gzip; then
        mv "${archive}.tmp" "${archive}"
        write_stamp success "${now}"
        last_restore="$(read_stamp restore)"
        if [ "$((now - last_restore))" -ge "${RESTORE_TEST_INTERVAL_SECONDS:-604800}" ]; then
            if restore_test "${archive}"; then
                write_stamp restore "$(date -u +%s)"
            else
                write_stamp failure "$(date -u +%s)"
            fi
        fi
    else
        write_stamp failure "$(date -u +%s)"
    fi
    publish_metrics
    sleep "${BACKUP_INTERVAL_SECONDS:-86400}"
done
