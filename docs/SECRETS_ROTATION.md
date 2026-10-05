# Local secrets and rotation

The root `.env` and `infrastructure/docker/.env` are ignored by Git. Copy
`.env.example` to the root `.env` for a new installation and fill in secrets
locally. Do not paste live values into issues, commits, or logs. Run
`python3 scripts/check_committed_secrets.py` before pushing changes.

Existing local credentials must be rotated at their issuers. Rotate the Groq
API key, Telegram bot token, YouTube/Google API key, MongoDB password, and
Grafana administrator password if their current values have been shared. An
old MongoDB URI was present in tracked backfill utilities, so its password
must be treated as exposed in Git history. For each provider, issue a
replacement, update the local secret, restart only the service that uses it,
verify its health, then revoke the old credential at the provider. Restart
Alertmanager after rotating the Telegram token because its rendered secret is
stored in a Docker volume. Check the Git history separately if secrets were
ever committed; `.gitignore` does not remove historical values.

Local Kafka uses an unauthenticated loopback listener for host tools and the
private Compose network for services. The ZooKeeper client port is no longer
published to the host. TLS/SASL and credential storage for a production Kafka
cluster belong to the production rollout.
