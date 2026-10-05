#!/bin/sh
set -eu

dataset="${BACKUP_DATASET}"
archive_dir="/backups/${dataset}"
metric_file="/backup-metrics/${dataset}.prom"
mkdir -p "${archive_dir}" /backup-metrics

read_stamp() {
    stamp_file="/backups/${dataset}-$1.stamp"
    if [ -f "${stamp_file}" ]; then
        sed -n '1p' "${stamp_file}"
    else
        printf '0'
    fi
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
    verify_db="${PGDATABASE}_restore_probe_$(date -u +%s)_$$"
    createdb --maintenance-db=postgres "${verify_db}" || return 1
    if pg_restore --exit-on-error --no-owner --no-acl -d "${verify_db}" "$1"; then
        table_count="$(psql -d "${verify_db}" -Atqc "SELECT count(*) FROM pg_catalog.pg_class WHERE relkind IN ('r', 'p') AND relnamespace NOT IN (SELECT oid FROM pg_catalog.pg_namespace WHERE nspname LIKE 'pg_%' OR nspname = 'information_schema')")"
    else
        table_count=0
    fi
    dropdb --maintenance-db=postgres "${verify_db}" || return 1
    [ "${table_count}" -gt 0 ]
}

publish_metrics
while :; do
    now="$(date -u +%s)"
    archive="${archive_dir}/${dataset}-${now}.dump"
    if pg_dump --format=custom --file="${archive}.tmp" && pg_restore --list "${archive}.tmp" >/dev/null; then
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
