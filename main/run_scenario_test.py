"""
Senaryo testi: mevcut hafta 3–12, lead time 6 (varsayılan).
Çıktı sütunları: mevcut haftada tahmin edilen *lead-time hedef haftası* için gerçekleşen,
hibrit ham tahmin (raw_forecast) ve bias düzeltilmiş tahmin (bias_corrected_forecast).

Orchestrator logları stdout’a yazılmaz; Chronos/torch kaynaklı uyarılar stderr’de görünebilir.

Usage (main/ içinden):
  python run_scenario_test.py --material-id M100F133RO
  python run_scenario_test.py --material-id M100F133RO --model-size small
"""

from __future__ import annotations

import argparse
import io
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path


def _main() -> None:
    parser = argparse.ArgumentParser(description="Hafta 3–12 lead time 6 senaryo özeti")
    parser.add_argument(
        "--material-id",
        type=str,
        default="M100F133RO",
        help="Material - Key",
    )
    parser.add_argument(
        "--data",
        type=str,
        default=None,
        help="Excel veya CSV yolu (varsayılan: stok_projesi/data_safety_stock.xlsx)",
    )
    parser.add_argument(
        "--model-size",
        type=str,
        default="bolt-base",
        choices=["bolt-tiny", "bolt-mini", "bolt-small", "bolt-base", "tiny", "mini", "small", "base", "large"],
    )
    parser.add_argument("--start-week", type=int, default=3)
    parser.add_argument("--end-week", type=int, default=12)
    parser.add_argument("--lead-time", type=int, default=6)
    parser.add_argument(
        "--use-column-forecast",
        action="store_true",
        default=False,
        help="Chronos tahmininde EDI sutun yakinsama serisini kullan",
    )
    args = parser.parse_args()

    data_path = args.data
    if not data_path:
        data_path = str(Path(__file__).resolve().parents[2] / "data_safety_stock.xlsx")
    if not os.path.isfile(data_path):
        print(f"HATA: Veri dosyası yok: {data_path}", file=sys.stderr)
        sys.exit(1)

    if str(data_path).lower().endswith((".xlsx", ".xls")):
        from excel_data_loader import ExcelDataLoader

        try:
            ExcelDataLoader.validate_material_code(data_path, args.material_id)
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(2)

    from orchestrator import StockPlanningOrchestrator

    buf = io.StringIO()
    with redirect_stdout(buf):
        orch = StockPlanningOrchestrator(
            chronos_model_size=args.model_size,
            use_column_forecast=args.use_column_forecast
        )
        try:
            orch.load_material_data(
                filepath=data_path,
                material_id=args.material_id,
                lead_time_weeks=args.lead_time,
            )
        except ValueError as e:
            print(str(e), file=sys.stderr)
            sys.exit(2)

        decisions = []
        for w in range(args.start_week, args.end_week + 1):
            d = orch.run_weekly_planning(args.material_id, current_week=w)
            decisions.append(d)

    # Yalnızca istenen sütunlar (stdout); Türkçe başlık için UTF-8
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    print("hafta\tgerçek\tham_tahmin\tdüzeltilmiş")
    for d in decisions:
        g = d.actual_target_week
        g_str = f"{g:.4g}" if g is not None else "-"
        print(f"{d.current_week}\t{g_str}\t{d.raw_forecast:.4g}\t{d.bias_corrected_forecast:.4g}")


if __name__ == "__main__":
    _main()
