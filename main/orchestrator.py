"""
Ana Orkestratör
Haftalık stok planlama sisteminin ana çalışma akışı
"""

import numpy as np
from typing import Dict, List, Optional
from datetime import datetime

from models import MaterialData, HorizonError, StockDecision
from chronos_forecaster import ChronosForecaster
from edi_processor import EDIProcessor
from stock_calculator import StockCalculator


class StockPlanningOrchestrator:
    """
    Dinamik Stok Planlama Sistemi Orkestratörü
    
    Haftalık çalışma akışı:
    1. Chronos ile ileri haftalar için talep tahmini
    2. Geçmiş verilerle horizon bazlı bias ve hata ölçüleri güncelleme
    3. Lead time'a denk gelen haftanın talebini düzeltme
    4. Emniyet stoğu ve reorder point hesaplama
    5. Sipariş kararı verme
    """
    
    def __init__(self, chronos_model_size: str = "base"):
        """
        Orkestratörü başlatır.
        
        Args:
            chronos_model_size: Chronos model boyutu
        """
        self.forecaster = ChronosForecaster(model_size=chronos_model_size)
        self.edi_processor = EDIProcessor()
        self.stock_calculator = StockCalculator()
        
        # Horizon bazlı hata cache'i
        self.horizon_errors: Dict[str, Dict[int, HorizonError]] = {}
        
        print("Stok Planlama Sistemi başlatıldı.")
    
    def load_material_data(
        self,
        filepath: str,
        material_id: str,
        lead_time_weeks: int,
        current_stock: float,
        service_level: float = 0.95
    ) -> MaterialData:
        """EDI verilerini yükler"""
        material = self.edi_processor.load_from_csv(
            filepath, material_id, lead_time_weeks, current_stock, service_level
        )
        
        # Horizon hatalarını hesapla
        self._update_horizon_errors(material_id)
        
        return material
    
    def _update_horizon_errors(self, material_id: str):
        """Horizon bazlı hataları günceller"""
        error_dict = self.edi_processor.calculate_forecast_errors(material_id)
        
        self.horizon_errors[material_id] = {}
        for horizon, metrics in error_dict.items():
            self.horizon_errors[material_id][horizon] = HorizonError(
                horizon=horizon,
                bias=metrics['bias'],
                rmse=metrics['rmse'],
                std=metrics['std'],
                sample_count=metrics['count']
            )
    
    def get_horizon_error(
        self,
        material_id: str,
        horizon: int
    ) -> Optional[HorizonError]:
        """Belirli bir horizon için hata metriklerini döner"""
        if material_id not in self.horizon_errors:
            return None
        
        material_errors = self.horizon_errors[material_id]
        
        # Tam horizon varsa onu kullan
        if horizon in material_errors:
            return material_errors[horizon]
        
        # En yakın horizon'u bul
        available_horizons = list(material_errors.keys())
        if not available_horizons:
            return None
        
        closest = min(available_horizons, key=lambda h: abs(h - horizon))
        return material_errors[closest]
    
    def run_weekly_planning(
        self,
        material_id: str,
        current_week: int
    ) -> StockDecision:
        """
        Haftalık planlama döngüsünü çalıştırır.
        
        Args:
            material_id: Malzeme ID
            current_week: Mevcut hafta numarası
            
        Returns:
            StockDecision objesi
        """
        material = self.edi_processor.materials.get(material_id)
        if not material:
            raise ValueError(f"Malzeme bulunamadı: {material_id}")
        
        print(f"\n{'='*60}")
        print(f"Haftalık Planlama - Malzeme: {material_id} | Hafta: {current_week}")
        print(f"{'='*60}")
        
        # 1. Geçmiş tüketim serisini al
        historical = self.edi_processor.get_historical_series(material_id, current_week)
        print(f"Geçmiş veri sayısı: {len(historical)}")
        
        # 2. Lead time için Chronos tahmini
        lead_time = material.lead_time_weeks
        print(f"Lead time: {lead_time} hafta")
        
        if len(historical) >= 2:
            # Chronos ile tahmin
            raw_forecast = self.forecaster.forecast_single_week(historical, lead_time)
            print(f"Chronos tahmini (ham): {raw_forecast:.2f}")
        else:
            # Yeterli veri yoksa EDI tahminini kullan
            latest_forecasts = self.edi_processor.get_latest_forecasts(material_id, current_week)
            target_week = current_week + lead_time
            raw_forecast = latest_forecasts.get(target_week, 0)
            print(f"EDI tahmini kullanıldı: {raw_forecast:.2f}")
        
        # 3. Horizon bazlı hata metriklerini al
        horizon_error = self.get_horizon_error(material_id, lead_time)
        if horizon_error:
            print(f"Horizon {lead_time} hata metrikleri:")
            print(f"  Bias: {horizon_error.bias:.2f}")
            print(f"  RMSE: {horizon_error.rmse:.2f}")
            print(f"  Std: {horizon_error.std:.2f}")
        else:
            print("Horizon hata metrikleri bulunamadı, varsayılan değerler kullanılacak.")
        
        # 4. Stok kararı oluştur
        decision = self.stock_calculator.make_stock_decision(
            material=material,
            current_week=current_week,
            raw_forecast=raw_forecast,
            horizon_error=horizon_error
        )
        
        # 5. Sonuçları yazdır
        print(f"\n{decision}")
        
        return decision
    
    def run_simulation(
        self,
        material_id: str,
        start_week: int,
        end_week: int,
        initial_stock: float
    ) -> List[StockDecision]:
        """
        Belirli bir dönem için simülasyon çalıştırır.
        
        Args:
            material_id: Malzeme ID
            start_week: Başlangıç haftası
            end_week: Bitiş haftası
            initial_stock: Başlangıç stok seviyesi
            
        Returns:
            Her hafta için stok kararları listesi
        """
        material = self.edi_processor.materials.get(material_id)
        if not material:
            raise ValueError(f"Malzeme bulunamadı: {material_id}")
        
        decisions = []
        current_stock = initial_stock
        actuals = material.get_actuals_dict()
        
        print(f"\n{'#'*60}")
        print(f"SİMÜLASYON BAŞLATILIYOR")
        print(f"Malzeme: {material_id}")
        print(f"Dönem: Hafta {start_week} - {end_week}")
        print(f"Başlangıç Stok: {initial_stock:.2f}")
        print(f"{'#'*60}")
        
        for week in range(start_week, end_week + 1):
            # Mevcut stoku güncelle
            material.current_stock = current_stock
            
            # Haftalık planlama
            decision = self.run_weekly_planning(material_id, week)
            decisions.append(decision)
            
            # Stok güncellemesi (simülasyon için)
            # Sipariş verdiyse, lead time sonra gelecek (şimdilik basitleştirilmiş)
            actual_consumption = actuals.get(week, 0)
            current_stock = max(0, current_stock - actual_consumption)
            
            # Sipariş geldiyse ekle (basitleştirilmiş: anında geliyor)
            if decision.should_order:
                current_stock += decision.recommended_order_qty
            
            print(f"Hafta {week} sonu stok: {current_stock:.2f}")
        
        # Özet
        print(f"\n{'#'*60}")
        print("SİMÜLASYON ÖZETİ")
        print(f"{'#'*60}")
        
        total_orders = sum(1 for d in decisions if d.should_order)
        total_qty = sum(d.recommended_order_qty for d in decisions)
        
        print(f"Toplam sipariş sayısı: {total_orders}")
        print(f"Toplam sipariş miktarı: {total_qty:.2f}")
        print(f"Final stok seviyesi: {current_stock:.2f}")
        
        return decisions
    
    def get_summary_report(
        self,
        material_id: str,
        decisions: List[StockDecision]
    ) -> Dict:
        """Özet rapor oluşturur"""
        if not decisions:
            return {}
        
        return {
            'material_id': material_id,
            'period': {
                'start_week': decisions[0].current_week,
                'end_week': decisions[-1].current_week
            },
            'orders': {
                'count': sum(1 for d in decisions if d.should_order),
                'total_quantity': sum(d.recommended_order_qty for d in decisions)
            },
            'inventory': {
                'avg_safety_stock': np.mean([d.safety_stock for d in decisions]),
                'avg_reorder_point': np.mean([d.reorder_point for d in decisions])
            },
            'service_level': decisions[0].service_level
        }
