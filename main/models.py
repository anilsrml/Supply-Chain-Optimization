"""
Veri modelleri ve yapıları
Data models and structures for the Dynamic Stock Planning System
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import date, datetime
import numpy as np


@dataclass
class EDIForecast:
    """Haftalık EDI tahmin verisi"""
    forecast_week: int  # Tahminin yapıldığı hafta
    target_week: int    # Tahmin edilen hafta
    quantity: float     # Tahmin miktarı
    
    @property
    def horizon(self) -> int:
        """Tahmin horizonu (kaç hafta ileri)"""
        return self.target_week - self.forecast_week


@dataclass
class ActualConsumption:
    """Gerçekleşen tüketim verisi"""
    week: int
    quantity: float


@dataclass
class MaterialData:
    """Malzeme verisi"""
    material_id: str
    lead_time_weeks: int  # Tedarik süresi (hafta)

    # EDI tahminleri ve gerçekleşen tüketimler
    edi_forecasts: List[EDIForecast] = field(default_factory=list)
    actual_consumptions: List[ActualConsumption] = field(default_factory=list)
    
    def get_forecast_matrix(self) -> Dict[int, Dict[int, float]]:
        """
        EDI tahmin matrisini oluşturur.
        Returns: {forecast_week: {target_week: quantity}}
        """
        matrix = {}
        for edi in self.edi_forecasts:
            if edi.forecast_week not in matrix:
                matrix[edi.forecast_week] = {}
            matrix[edi.forecast_week][edi.target_week] = edi.quantity
        return matrix
    
    def get_actuals_dict(self) -> Dict[int, float]:
        """Gerçekleşen tüketimleri dictionary olarak döner"""
        return {ac.week: ac.quantity for ac in self.actual_consumptions}


@dataclass
class HorizonError:
    """Horizon bazlı hata metrikleri"""
    horizon: int
    bias: float  # Ortalama bias (tahmin - gerçekleşen)
    rmse: float  # Root Mean Square Error
    std: float   # Standart sapma
    sample_count: int  # Örnek sayısı


@dataclass
class ChronosForecastLog:
    """Chronos tahmin geçmişi kaydı"""
    material_id: str
    forecast_week: int
    target_week: int
    forecast_value: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    @property
    def horizon(self) -> int:
        """Tahmin horizonu (kaç hafta ileri)"""
        return self.target_week - self.forecast_week


@dataclass
class StockDecision:
    """Stok kararı sonucu"""
    material_id: str
    current_week: int
    
    # Tahmin değerleri
    lead_time_week: int  # Lead time sonundaki hedef hafta
    raw_forecast: float  # Ham Chronos tahmini
    bias_corrected_forecast: float  # Bias düzeltilmiş tahmin
    
    # Metrikler
    horizon_error: Optional[HorizonError] = None
    actual_target_week: Optional[float] = None  # Hedef haftanın gerçek değeri (eğer varsa)
    
    # Hibrit sistem bilgileri
    selected_source: str = "EDI"  # Seçilen tahmin kaynağı: "CHRONOS", "EDI", "HYBRID"
    chronos_raw_forecast: Optional[float] = None  # Chronos'un ham tahmini
    edi_raw_forecast: Optional[float] = None  # EDI'nin ham tahmini
    
    def __str__(self) -> str:
        # Hedef hafta bilgisi
        target_week_info = f"Lead Time Hedef Hafta: {self.lead_time_week}"
        if self.actual_target_week is not None:
            target_week_info += f" | Gerçek Değer: {self.actual_target_week:.2f}"
        else:
            target_week_info += " | Gerçek Değer: Henüz Bilinmiyor"

        # Kaynak bilgisi
        source_info = f"Seçilen Kaynak: {self.selected_source}"
        if self.chronos_raw_forecast is not None and self.edi_raw_forecast is not None:
            source_info += f" | Chronos: {self.chronos_raw_forecast:.2f}, EDI: {self.edi_raw_forecast:.2f}"

        return (
            f"Malzeme: {self.material_id} | Hafta: {self.current_week}\n"
            f"{target_week_info}\n"
            f"{source_info}\n"
            f"Ham Tahmin: {self.raw_forecast:.2f} | Düzeltilmiş: {self.bias_corrected_forecast:.2f}"
        )
