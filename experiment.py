"""Запуск монитора и ограниченной по времени нагрузки в отдельных процессах."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime
import psutil

ROOT = Path(__file__).parent


def main():
    (ROOT / "evidence").mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    memory = psutil.virtual_memory()
    # Не более половины RAM и четверти доступной памяти; максимум 512 МиБ.
    amount = min(512 * 1024**2, memory.total // 2, memory.available // 4)
    events = {"started_at": datetime.now().isoformat(), "ram_total": memory.total,
              "available_before": memory.available, "allocated_bytes": amount,
              "reason": "Нагрузка уменьшена относительно 2 ГиБ для сохранения запаса свободной RAM"}
    children = []
    with (ROOT / "evidence/monitor_load.txt").open("w", encoding="utf-8") as out:
        monitor = subprocess.Popen([sys.executable, "-u", str(ROOT / "monitor.py"), "--variant", "1", "--output", str(ROOT / "monitor_log.csv")], stdout=out, stderr=subprocess.STDOUT, env=env)
        try:
            time.sleep(5)
            cpu_code = "import time, os; from pathlib import Path; " + f"Path({str(ROOT / 'evidence/cpu_ready.txt')!r}).write_text(str(os.getpid())); " + "end=time.monotonic()+35\nwhile time.monotonic()<end: pass"
            cpu = subprocess.Popen([sys.executable, "-c", cpu_code], env=env)
            children.append(cpu)
            events["cpu"] = {"pid": cpu.pid, "started_at": datetime.now().isoformat(), "threads": 1}
            mem_code = "import time, os; from pathlib import Path; " + f"a=bytearray({amount}); Path({str(ROOT / 'evidence/memory_ready.txt')!r}).write_text(str(os.getpid())); time.sleep(35)"
            mem = subprocess.Popen([sys.executable, "-c", mem_code], env=env)
            children.append(mem)
            events["memory"] = {"pid": mem.pid, "started_at": datetime.now().isoformat()}
            (ROOT / "evidence/load_events.json").write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
            monitor.wait(timeout=45)
            events["monitor_exit_code"] = monitor.returncode
            actual_cpu = int((ROOT / "evidence/cpu_ready.txt").read_text())
            actual_mem = int((ROOT / "evidence/memory_ready.txt").read_text())
            events["cpu"]["worker_pid"] = actual_cpu
            events["memory"]["worker_pid"] = actual_mem
            events["cpu_time_seconds"] = psutil.Process(actual_cpu).cpu_times().user
            events["memory_rss_bytes"] = psutil.Process(actual_mem).memory_info().rss
        finally:
            for child in children:
                if child.poll() is None:
                    for worker in psutil.Process(child.pid).children(recursive=True):
                        worker.terminate()
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=5)
            if monitor.poll() is None:
                monitor.terminate()
                monitor.wait(timeout=5)
            events["finished_at"] = datetime.now().isoformat()
            events["load_processes_stopped"] = all(c.poll() is not None for c in children)
            (ROOT / "evidence/load_events.json").write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(events, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
