"""ЛР4. Мониторинг CPU, RAM, диска и метрики выбранного варианта."""
import argparse
import csv
import json
import os
from pathlib import Path
from statistics import mean
import time
from datetime import datetime

import psutil

INTERVAL = 1
SAMPLES = 30
THRESHOLDS = {"cpu": 70, "ram": 80, "disk": 85}
EXTRA_METRIC = "processes"
VARIANTS = {1: (INTERVAL, SAMPLES, tuple(THRESHOLDS.values()), EXTRA_METRIC)}
DISK_PATH = Path(os.environ.get("SystemDrive", "C:" ) + "\\") if os.name == "nt" else Path("/")


def extra_metric(name):
    if name != "processes":
        raise ValueError(name)
    return len(psutil.pids())


def take_sample(extra):
    value = extra_metric(extra)
    return {
        "time": datetime.now().isoformat(timespec="seconds"),
        "cpu": psutil.cpu_percent(interval=None),
        "ram": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage(str(DISK_PATH)).percent,
        extra: round(value, 3) if value is not None else None,
    }


def check_alerts(sample, thresholds):
    return [f"{metric.upper()} = {sample[metric]}% (порог {limit}%)"
            for metric, limit in thresholds.items() if sample[metric] >= limit]


def summarize(samples, extra):
    result = {}
    for metric in ("cpu", "ram", "disk", extra):
        values = [s[metric] for s in samples if s[metric] is not None]
        result[metric] = {"mean": round(mean(values), 3), "max": max(values),
                          "min": min(values)} if values else None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", type=int, default=1, choices=VARIANTS)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("monitor_log.csv"))
    args = parser.parse_args()
    interval, count, limits, extra = VARIANTS[args.variant]
    thresholds = dict(zip(("cpu", "ram", "disk"), limits))
    print(f"Вариант {args.variant}; интервал {interval} с; замеров {count}; пороги {thresholds}; метрика {extra}", flush=True)
    print(f"Диск: {DISK_PATH}", flush=True)
    psutil.cpu_percent(interval=None)
    psutil.cpu_percent(interval=None, percpu=True)
    samples = []
    with args.output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["time", "cpu", "ram", "disk", extra, "alert"])
        writer.writeheader()
        for _ in range(count):
            time.sleep(interval)
            sample = take_sample(extra)
            sample["alert"] = "; ".join(check_alerts(sample, thresholds))
            writer.writerow(sample)
            f.flush()
            samples.append(sample)
            mark = " <-- ВНИМАНИЕ: " + sample["alert"] if sample["alert"] else ""
            print(f"{sample['time']} CPU {sample['cpu']:5.1f}% RAM {sample['ram']:5.1f}% DISK {sample['disk']:5.1f}% {extra}={sample[extra]}{mark}", flush=True)
    stats = summarize(samples, extra)
    print("\nСТАТИСТИКА: среднее / максимум / минимум", flush=True)
    for metric, values in stats.items():
        print(f"{metric}: {values['mean']:.3f} / {values['max']:.3f} / {values['min']:.3f}" if values else f"{metric}: недоступно", flush=True)
    result = {"variant": args.variant, "interval": interval, "samples": count,
              "thresholds": thresholds, "extra_metric": extra, "statistics": stats,
              "first_alert": next((s for s in samples if s["alert"]), None)}
    args.output.with_suffix(".summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Журнал сохранён в {args.output.name}", flush=True)


if __name__ == "__main__":
    main()
