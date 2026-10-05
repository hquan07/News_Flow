from infrastructure.monitoring.render_alertmanager import build_config


def test_alertmanager_routes_severity_and_component(tmp_path):
    config = build_config(
        {
            "TELEGRAM_BOT_TOKEN": "test-only-token",
            "TELEGRAM_CHAT_ID": "123",
            "MONITORING_DATABASE_CHAT_ID": "456",
            "PAGERDUTY_ROUTING_KEY": "test-only-key",
        },
        tmp_path,
    )

    routes = config["route"]["routes"]
    assert [route["matchers"] for route in routes] == [
        ['severity="warning"'],
        ['severity="critical"'],
        ['severity="emergency"'],
    ]
    assert routes[1]["routes"][0]["matchers"] == ['component="database"']
    receivers = {receiver["name"]: receiver for receiver in config["receivers"]}
    assert receivers["database-critical"]["telegram_configs"][0]["chat_id"] == 456
    assert "pagerduty_configs" in receivers["emergency"]
    assert "test-only-token" not in str(config)
    assert "test-only-key" not in str(config)


def test_alertmanager_starts_without_notification_credentials(tmp_path):
    config = build_config({}, tmp_path)

    assert config["route"]["receiver"] == "dashboard-only"
    assert config["receivers"][1] == {"name": "warning"}
