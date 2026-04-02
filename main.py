"""
Repo kökünden çalıştırmak için kolay giriş noktası.

Kullanım (kök dizinde):
  python main.py --data "data.csv" --current-week 7 --lead-time 6 --current-stock 0 --model-size large

Not:
- Asıl CLI `main/main.py` içindedir.
- `--data` için "data.csv" gibi göreli bir yol verilirse ve kökte bulunamazsa,
  otomatik olarak `main/data.csv` altında da aranır.
"""

from __future__ import annotations

import os
import runpy
import sys


def _rewrite_data_arg_if_needed(repo_root: str) -> None:
    """`--data` argümanını gerekirse `main/` altına yönlendirir."""
    argv = sys.argv
    if "--data" not in argv:
        return

    i = argv.index("--data")
    if i + 1 >= len(argv):
        return

    data_path = argv[i + 1]
    # Kullanıcı zaten tam yol veya mevcut yol verdiyse dokunma
    if os.path.isabs(data_path) or os.path.exists(data_path):
        return

    candidate = os.path.join(repo_root, "main", data_path)
    if os.path.exists(candidate):
        argv[i + 1] = candidate
        return

    # `data_safety_stock.xlsx` gibi dosyalar repo üstünde (stok_projesi/) olabilir
    parent_root = os.path.dirname(repo_root)
    candidate_parent = os.path.join(parent_root, data_path)
    if os.path.exists(candidate_parent):
        argv[i + 1] = candidate_parent


def main() -> None:
    # Windows terminalinde Türkçe karakterler bozulmasın diye UTF-8 çıktı kullan.
    # (Terminal font/codepage desteklemiyorsa yine bozulabilir, ama çoğu durumda düzeltir.)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    repo_root = os.path.dirname(os.path.abspath(__file__))
    main_dir = os.path.join(repo_root, "main")

    # `main/main.py` içindeki `from orchestrator import ...` gibi importlar için
    # `main/` klasörünü sys.path'e ekle.
    if main_dir not in sys.path:
        sys.path.insert(0, main_dir)

    _rewrite_data_arg_if_needed(repo_root)

    target = os.path.join(main_dir, "main.py")
    runpy.run_path(target, run_name="__main__")


if __name__ == "__main__":
    main()

