"""
Excel (data_safety_stock.xlsx) formatından EDI üst üçgen matrisi üretir.

Sütunlar: Material - Key, Material, Plant, Record Date, haftalık tarih başlıkları, Sum: (yoksayılır).
Tarihler W1, W2, ... olacak şekilde numaralandırılır (tüm satır/sütun tarihlerinin birleşimi, en erken = W1).
Gerçekleşen tüketim EDIProcessor.load_from_dataframe içinde köşegen değil, köşegenin bir altı (fw=tw+1) olarak okunur.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, List, Set, Union

import numpy as np
import pandas as pd


def _norm_col(s: str) -> str:
    return " ".join(str(s).strip().lower().replace("-", " ").split())


def _to_ts_key(val: Any) -> pd.Timestamp:
    t = pd.to_datetime(val, errors="coerce")
    if pd.isna(t):
        raise ValueError(f"Tarih çözümlenemedi: {val!r}")
    return pd.Timestamp(t.normalize())


def _col_is_ignored(name: Any) -> bool:
    s = str(name).strip().lower()
    return s.startswith("sum") or s.startswith("unnamed:")


def _col_is_week_header(name: Any) -> bool:
    if _col_is_ignored(name):
        return False
    if isinstance(name, pd.Timestamp):
        return True
    if isinstance(name, datetime):
        return True
    if hasattr(name, "strftime") and not isinstance(name, str):
        try:
            _to_ts_key(name)
            return True
        except ValueError:
            return False
    if isinstance(name, (int, float)) and not isinstance(name, bool):
        return False
    if isinstance(name, str):
        if _col_is_ignored(name):
            return False
        try:
            _to_ts_key(name)
            return True
        except ValueError:
            return False
    return False


def _find_first_matching_column(df: pd.DataFrame, *must_contain: str) -> str:
    must = tuple(_norm_col(x) for x in must_contain)
    for c in df.columns:
        key = _norm_col(str(c))
        if all(part in key for part in must):
            return c  # type: ignore[return-value]
    raise ValueError(f"Gerekli sütun bulunamadı (içermeli: {must_contain}). Mevcut: {list(df.columns)[:20]}...")


class ExcelDataLoader:
    """data_safety_stock.xlsx → hafta numaralı EDI DataFrame (index/sütun = 1..N)."""

    @staticmethod
    def _validate_material_in_frame(df: pd.DataFrame, material_id: str) -> str:
        """DataFrame içinde materyal kodu doğrulanır; normalize edilmiş kodu döner."""
        key_col = _find_first_matching_column(df, "material", "key")
        want = str(material_id).strip()
        codes_in_file = (
            df[key_col]
            .dropna()
            .astype(str)
            .str.strip()
        )
        if want in set(codes_in_file):
            return want
        valid = sorted(codes_in_file.unique().tolist())
        preview = ", ".join(valid[:15])
        more = f" (+{len(valid) - 15} daha)" if len(valid) > 15 else ""
        raise ValueError(
            f"Geçersiz materyal kodu: '{material_id}'. "
            f"Bu dosyada böyle bir kod yok. Tahmin çalıştırılmadı. "
            f"Örnek kodlar: {preview}{more}"
        )

    @staticmethod
    def validate_material_code(excel_path: Union[str, Path], material_id: str) -> None:
        """Dosyada yoksa ValueError (Chronos yüklenmeden önce CLI’da kullanılır)."""
        path = Path(excel_path)
        if not path.is_file():
            raise FileNotFoundError(f"Excel bulunamadı: {path}")
        df = pd.read_excel(path, header=0, engine="openpyxl")
        ExcelDataLoader._validate_material_in_frame(df, material_id)

    @staticmethod
    def list_material_codes(excel_path: Union[str, Path]) -> List[str]:
        df = pd.read_excel(excel_path, header=0, engine="openpyxl")
        key_col = _find_first_matching_column(df, "material", "key")
        codes = (
            df[key_col]
            .dropna()
            .astype(str)
            .str.strip()
        )
        return sorted(codes.unique().tolist())

    @staticmethod
    def build_edi_dataframe(
        excel_path: Union[str, Path],
        material_id: str,
    ) -> pd.DataFrame:
        path = Path(excel_path)
        if not path.is_file():
            raise FileNotFoundError(f"Excel bulunamadı: {path}")

        df = pd.read_excel(path, header=0, engine="openpyxl")
        key_col = _find_first_matching_column(df, "material", "key")
        record_col = _find_first_matching_column(df, "record", "date")

        want = ExcelDataLoader._validate_material_in_frame(df, material_id)

        codes_in_file = (
            df[key_col]
            .dropna()
            .astype(str)
            .str.strip()
        )

        mat_rows = df[codes_in_file == want].copy()
        if mat_rows.empty:
            raise ValueError(f"Materyal '{material_id}' filtrelendi ama satır kalmadı.")

        forecast_cols: List[Any] = []
        for c in mat_rows.columns:
            if c == key_col or c == record_col:
                continue
            if _col_is_week_header(c):
                forecast_cols.append(c)

        if not forecast_cols:
            raise ValueError(
                "Haftalık tarih sütunları bulunamadı (Excel başlıklarında tarih yok veya Sum sonrası)."
            )

        dates_set: Set[pd.Timestamp] = set()
        for _, row in mat_rows.iterrows():
            try:
                dates_set.add(_to_ts_key(row[record_col]))
            except ValueError:
                continue
        for c in forecast_cols:
            dates_set.add(_to_ts_key(c))

        sorted_dates = sorted(dates_set)
        n = len(sorted_dates)
        date_to_week: dict[pd.Timestamp, int] = {d: i + 1 for i, d in enumerate(sorted_dates)}

        matrix = pd.DataFrame(np.nan, index=range(1, n + 1), columns=range(1, n + 1))

        grouped = mat_rows.groupby(record_col, sort=False, dropna=False)
        for rec_raw, sub in grouped:
            try:
                fw = date_to_week[_to_ts_key(rec_raw)]
            except (ValueError, KeyError):
                continue
            for col in forecast_cols:
                try:
                    tw = date_to_week[_to_ts_key(col)]
                except (ValueError, KeyError):
                    continue
                vals = pd.to_numeric(sub[col], errors="coerce")
                val = float(vals.sum()) if vals.notna().any() else np.nan
                if pd.notna(val):
                    matrix.loc[fw, tw] = val

        matrix.index = matrix.index.astype(int)
        matrix.columns = matrix.columns.astype(int)
        return matrix
