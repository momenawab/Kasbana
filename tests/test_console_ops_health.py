from console_ops.health import evaluate


def test_healthy_host_scores_100():
    score, status, penalties = evaluate(
        {
            "available": True,
            "server": {"cpu_percent": 18, "ram_percent": 42, "disk_percent": 31},
            "docker": {"stopped": 0, "restarting": 0},
        },
        {
            "cpu_warning": 80,
            "cpu_critical": 90,
            "ram_warning": 80,
            "ram_critical": 90,
            "disk_warning": 80,
            "disk_critical": 90,
        },
    )
    assert (score, status, penalties) == (100, "healthy", [])


def test_unavailable_collector_is_critical():
    score, status, penalties = evaluate(
        {"available": False, "server": {}, "docker": {}},
        {
            "cpu_warning": 80,
            "cpu_critical": 90,
            "ram_warning": 80,
            "ram_critical": 90,
            "disk_warning": 80,
            "disk_critical": 90,
        },
    )
    assert score <= 20 and status == "critical"
