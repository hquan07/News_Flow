"""Render Alertmanager routing from environment without logging credentials."""

import json
import os
from pathlib import Path


COMPONENT_CHAT_VARS = {
    "infrastructure": "MONITORING_INFRA_CHAT_ID",
    "api": "MONITORING_API_CHAT_ID",
    "streaming": "MONITORING_STREAMING_CHAT_ID",
    "data-platform": "MONITORING_DATA_CHAT_ID",
    "database": "MONITORING_DATABASE_CHAT_ID",
    "backup": "MONITORING_BACKUP_CHAT_ID",
}


def _chat_id(value: str | None) -> int | None:
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError("Monitoring chat ID must be an integer") from exc


def _secret_file(directory: Path, name: str, value: str) -> str:
    path = directory / name
    path.write_text(value, encoding="utf-8")
    path.chmod(0o444)
    return f"/etc/alertmanager/{name}"


def build_config(environ: dict[str, str], directory: Path) -> dict:
    token = environ.get("TELEGRAM_BOT_TOKEN", "")
    default_chat = _chat_id(environ.get("TELEGRAM_CHAT_ID"))
    telegram_token_file = (
        _secret_file(directory, "telegram-token", token) if token and default_chat else None
    )
    pagerduty_key = environ.get("PAGERDUTY_ROUTING_KEY", "")
    pagerduty_key_file = (
        _secret_file(directory, "pagerduty-key", pagerduty_key) if pagerduty_key else None
    )

    smtp_host = environ.get("MONITORING_SMTP_SMARTHOST", "")
    smtp_from = environ.get("MONITORING_SMTP_FROM", "")
    email_to = environ.get("MONITORING_EMAIL_TO", "")
    email_enabled = bool(smtp_host and smtp_from and email_to)

    global_config = {"resolve_timeout": "5m"}
    if email_enabled:
        global_config.update({"smtp_smarthost": smtp_host, "smtp_from": smtp_from})
        if environ.get("MONITORING_SMTP_USERNAME"):
            global_config["smtp_auth_username"] = environ["MONITORING_SMTP_USERNAME"]
        if environ.get("MONITORING_SMTP_PASSWORD"):
            global_config["smtp_auth_password_file"] = _secret_file(
                directory, "smtp-password", environ["MONITORING_SMTP_PASSWORD"]
            )

    receivers = [{"name": "dashboard-only"}]

    def add_receiver(name: str, severity: str, chat_id: int | None) -> None:
        receiver: dict = {"name": name}
        if telegram_token_file and chat_id is not None:
            receiver["telegram_configs"] = [{
                "bot_token_file": telegram_token_file,
                "chat_id": chat_id,
                "parse_mode": "",
                "send_resolved": True,
            }]
        if email_enabled and severity in ("critical", "emergency"):
            receiver["email_configs"] = [{"to": email_to, "send_resolved": True}]
        if pagerduty_key_file and severity == "emergency":
            receiver["pagerduty_configs"] = [{
                "routing_key_file": pagerduty_key_file,
                "severity": "critical",
                "send_resolved": True,
            }]
        receivers.append(receiver)

    routes = []
    for severity, wait in (("warning", "2m"), ("critical", "30s"), ("emergency", "0s")):
        add_receiver(severity, severity, default_chat)
        severity_route = {
            "receiver": severity,
            "matchers": [f'severity="{severity}"'],
            "group_wait": wait,
            "routes": [],
        }
        for component, var in COMPONENT_CHAT_VARS.items():
            team_chat = _chat_id(environ.get(var))
            if telegram_token_file and team_chat is not None:
                name = f"{component}-{severity}"
                add_receiver(name, severity, team_chat)
                severity_route["routes"].append({
                    "receiver": name,
                    "matchers": [f'component="{component}"'],
                })
        routes.append(severity_route)

    return {
        "global": global_config,
        "route": {
            "receiver": "dashboard-only",
            "group_by": ["alertname", "component", "instance"],
            "group_wait": "30s",
            "group_interval": "5m",
            "repeat_interval": "4h",
            "routes": routes,
        },
        "receivers": receivers,
        "inhibit_rules": [
            {
                "source_matchers": [f'alertname="{critical}"'],
                "target_matchers": [f'alertname="{warning}"'],
                "equal": equal,
            }
            for warning, critical, equal in (
                ("HostDiskWarning", "HostDiskCritical", ["instance", "mountpoint"]),
                ("HostDiskCritical", "HostDiskEmergency", ["instance", "mountpoint"]),
                ("HostCPUWarning", "HostCPUCritical", ["instance"]),
                ("HostMemoryWarning", "HostMemoryCritical", ["instance"]),
                ("APIErrorRateWarning", "APIErrorRateCritical", []),
                ("APILatencyP95Warning", "APILatencyP95Critical", []),
                ("KafkaConsumerLagWarning", "KafkaConsumerLagCritical", ["consumergroup"]),
                ("DiskPredicted90PercentWithin14Days", "DiskPredicted90PercentWithin5Days", ["instance", "mountpoint"]),
            )
        ],
    }


def main() -> None:
    directory = Path(os.getenv("ALERTMANAGER_OUTPUT_DIR", "/generated"))
    directory.mkdir(parents=True, exist_ok=True)
    config = build_config(dict(os.environ), directory)
    output = directory / "alertmanager.yml"
    output.write_text(json.dumps(config, indent=2), encoding="utf-8")
    output.chmod(0o444)


if __name__ == "__main__":
    main()
