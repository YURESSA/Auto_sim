"""Eight straightforward one-year runs for the student report."""
from dataclasses import replace, asdict
import json
from pathlib import Path
from simulator import Config, Simulation

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output" / "student_report"
BASE = Config(days=365, seed=2025, inventory_mode=True, stock_source="Ханко")


def cases():
    def stock(n, **kw):
        return replace(BASE, initial=n, target=n, reorder=max(0, n - 1), replenish=n > 0, **kw)
    return [
        ("Без запаса", stock(0)),
        ("Ханко запас 5", stock(5)),
        ("Ханко запас 8", stock(8)),
        ("Ханко запас 10", stock(10)),
        ("Москва запас 8", stock(8, stock_source="Москва")),
        ("Без запаса предоплата 50%", stock(0, prepay=.5)),
        ("Ханко запас 8 предоплата 50%", stock(8, prepay=.5)),
        ("Ханко запас 8 железная дорога", stock(8, rail=True)),
    ]


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, cfg in cases():
        sim = Simulation(cfg).run()
        rows.append({"name": name, "config": asdict(cfg), "result": sim.summary()})
        print(name, sim.summary()["profit"], flush=True)
    (OUT / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows


if __name__ == "__main__":
    run()
