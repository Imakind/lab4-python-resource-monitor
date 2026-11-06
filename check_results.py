"""Проверка логики на тестовых данных без сбора личных сетевых параметров."""
import copy
import csv
import json
from pathlib import Path
import socket
from collections import namedtuple
from unittest.mock import patch

import psutil
from inventory import analyze, get_network_info
from monitor import check_alerts, summarize


def main():
    base = {"cpu": {"physical_cores": 6},
            "memory": {"total_gb": 16, "used_percent": 50},
            "disks": [{"device": "TEST_DISK", "used_percent": 85}]}
    assert len(analyze(base)) == 1
    p = copy.deepcopy(base)
    p["memory"].update(total_gb=7.9, used_percent=80)
    p["cpu"]["physical_cores"] = 3
    p["disks"][0]["used_percent"] = 85.1
    assert len(analyze(p)) == 4
    assert len(check_alerts({"cpu": 70, "ram": 79, "disk": 84},
                            {"cpu": 70, "ram": 80, "disk": 85})) == 1
    stats = summarize([{"cpu": 10, "ram": 20, "disk": 30, "x": None},
                       {"cpu": 30, "ram": 40, "disk": 50, "x": None}], "x")
    assert stats["cpu"] == {"mean": 20, "max": 30, "min": 10}
    assert stats["x"] is None
    addr = namedtuple("Addr", "family address netmask")
    fixtures = {
        "no_ipv4": [addr(psutil.AF_LINK, "TEST_MAC_A", None)],
        "test": [addr(socket.AF_INET, "TEST_IPV4", "TEST_MASK"),
                 addr(psutil.AF_LINK, "TEST_MAC_B", None)],
    }
    with patch("inventory.psutil.net_if_addrs", return_value=fixtures):
        assert get_network_info() == [{"name": "test", "ipv4": "TEST_IPV4",
                                      "netmask": "TEST_MASK", "mac": "TEST_MAC_B"}]
    root = Path(__file__).parent / "results"
    for name in ("monitor_baseline", "monitor_log"):
        with (root / f"{name}.csv").open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        expected = json.loads((root / f"{name}.summary.json").read_text(encoding="utf-8"))
        assert len(rows) == 30
        numeric = [{key: float(row[key]) for key in ("cpu", "ram", "disk", "processes")} for row in rows]
        assert summarize(numeric, "processes") == expected["statistics"]
    print("PASS: analysis rules, alert thresholds, summary statistics, network mocks")
    print("PASS: both published CSV files have 30 samples and matching statistics")


if __name__ == "__main__":
    main()
