"""
Stok Hesaplama Modülü
Safety Stock, Reorder Point ve sipariş kararları
"""

import numpy as np
from scipy import stats
from typing import Optional, Tuple
from models import HorizonError, StockDecision, MaterialData


class StockCalculator:
    """Emniyet stoğu ve yeniden sipariş noktası hesaplayan sınıf"""
    
    @staticmethod
    def get_z_score(service_level: float) -> float:
        """
        Servis seviyesine karşılık gelen Z değerini hesaplar.
        
        Args:
            service_level: Servis seviyesi (0-1 arası, örn: 0.95)
            
        Returns:
            Z skoru
        """
        return stats.norm.ppf(service_level)
    
    @staticmethod
    def calculate_safety_stock(
        demand_std: float,
        service_level: float = 0.95,
        lead_time_weeks: int = 1
    ) -> float:
        """
        Emniyet stoğu hesaplar.
        
        Safety Stock = Z * σ * √(Lead Time)
        
        Args:
            demand_std: Talep standart sapması (veya tahmin hatası std)
            service_level: Hedef servis seviyesi
            lead_time_weeks: Tedarik süresi (hafta)
            
        Returns:
            Emniyet stoğu miktarı
        """
        z_score = StockCalculator.get_z_score(service_level)
        safety_stock = z_score * demand_std * np.sqrt(lead_time_weeks)
        return max(0, safety_stock)
    
    @staticmethod
    def calculate_safety_stock_with_horizon_error(
        horizon_error: HorizonError,
        service_level: float = 0.95
    ) -> Tuple[float, float]:
        """
        Horizon bazlı hata ile emniyet stoğu hesaplar.
        
        Args:
            horizon_error: Horizon hata metrikleri
            service_level: Hedef servis seviyesi
            
        Returns:
            Tuple of (safety_stock, z_score)
        """
        z_score = StockCalculator.get_z_score(service_level)
        
        # RMSE veya std kullan (hangisi büyükse)
        uncertainty = max(horizon_error.rmse, horizon_error.std)
        
        safety_stock = z_score * uncertainty
        return max(0, safety_stock), z_score
    
    @staticmethod
    def calculate_reorder_point(
        lead_time_demand: float,
        safety_stock: float,
        bias: float = 0
    ) -> float:
        """
        Yeniden sipariş noktası hesaplar.
        
        Reorder Point = Lead Time Demand (bias corrected) + Safety Stock
        
        Args:
            lead_time_demand: Lead time boyunca beklenen talep
            safety_stock: Emniyet stoğu
            bias: Tahmin bias'ı (pozitif = over-forecast, negatif = under-forecast)
            
        Returns:
            Reorder point değeri
        """
        # Bias düzeltmesi: Tahmin yüksekse (pozitif bias) talebi düşür
        corrected_demand = lead_time_demand - bias
        
        return max(0, corrected_demand + safety_stock)
    
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
        bias = 0
        if horizon_error:
            bias = horizon_error.bias
        
        corrected_forecast = raw_forecast - bias
        
        # Safety stock hesapla
        if horizon_error:
            safety_stock, z_score = StockCalculator.calculate_safety_stock_with_horizon_error(
                horizon_error, material.service_level
            )
        else:
            # Varsayılan belirsizlik: tahmin değerinin %20'si
            default_std = raw_forecast * 0.2
            z_score = StockCalculator.get_z_score(material.service_level)
            safety_stock = z_score * default_std
        
        # Reorder point
        reorder_point = corrected_forecast + safety_stock
        
        # Sipariş kararı
        should_order = material.current_stock < reorder_point
        
        # Önerilen sipariş miktarı: Reorder point'e kadar doldurmak için gereken miktar
        recommended_qty = max(0, reorder_point - material.current_stock) if should_order else 0
        
        # Hedef haftanın gerçek değerini al (eğer varsa)
        actuals = material.get_actuals_dict()
        actual_target_week = actuals.get(lead_time_week)
        
        return StockDecision(
            material_id=material.material_id,
            current_week=current_week,
            lead_time_week=lead_time_week,
            raw_forecast=raw_forecast,
            bias_corrected_forecast=corrected_forecast,
            safety_stock=safety_stock,
            reorder_point=reorder_point,
            current_stock=material.current_stock,
            should_order=should_order,
            recommended_order_qty=recommended_qty,
            horizon_error=horizon_error,
            service_level=material.service_level,
            z_score=z_score,
            actual_target_week=actual_target_week
        )
    
    @staticmethod
    def calculate_stockout_probability(
        current_stock: float,
        expected_demand: float,
        demand_std: float
    ) -> float:
        """
        Stok tükenme olasılığını hesaplar.
        
        Args:
            current_stock: Mevcut stok
            expected_demand: Beklenen talep
            demand_std: Talep standart sapması
            
        Returns:
            Stok tükenme olasılığı (0-1)
        """
        if demand_std <= 0:
            return 0.0 if current_stock >= expected_demand else 1.0
        
        # Z-score: (Current Stock - Expected Demand) / Std
        z = (current_stock - expected_demand) / demand_std
        
        # Stok tükenme olasılığı = P(Demand > Current Stock)
        stockout_prob = 1 - stats.norm.cdf(z)
        
        return float(stockout_prob)
