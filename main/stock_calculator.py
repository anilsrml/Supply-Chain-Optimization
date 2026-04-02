"""
Stok Hesaplama Modülü
Tahmin tabanlı sipariş kararları
"""

import numpy as np
from typing import Optional
from models import HorizonError, StockDecision, MaterialData


class StockCalculator:
    """Tahmin tabanlı stok kararı oluşturan sınıf"""

    @staticmethod
    def make_stock_decision(
        material: MaterialData,
        current_week: int,
        raw_forecast: float,
        horizon_error: Optional[HorizonError] = None
    ) -> StockDecision:
        """
        Stok kararı oluşturur.

        Args:
            material: Malzeme verisi
            current_week: Mevcut hafta
            raw_forecast: Ham Chronos tahmini (lead time sonundaki talep)
            horizon_error: Horizon bazlı hata metrikleri

        Returns:
            StockDecision objesi
        """
        lead_time_week = current_week + material.lead_time_weeks

        # Bias düzeltmesi
        bias = horizon_error.bias if horizon_error else 0
        corrected_forecast = raw_forecast - bias

        # Hedef haftanın gerçek değerini al (eğer varsa)
        actuals = material.get_actuals_dict()
        actual_target_week = actuals.get(lead_time_week)

        return StockDecision(
            material_id=material.material_id,
            current_week=current_week,
            lead_time_week=lead_time_week,
            raw_forecast=raw_forecast,
            bias_corrected_forecast=corrected_forecast,
            horizon_error=horizon_error,
            actual_target_week=actual_target_week
        )
