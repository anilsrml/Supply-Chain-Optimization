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
    
    def __init__(self, chronos_model_size: str = "tiny"):
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
        
        # Chronos tahmin geçmişini yükle (hibrit sistem için)
        self.chronos_history = self.edi_processor.load_chronos_forecasts()
        
        print("Stok Planlama Sistemi başlatıldı (Hibrit Mod).")
    
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
        Haftalık planlama döngüsünü çalıştırır (Hibrit Sistem).
        
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
        
        # 2. Lead time ve hedef hafta
        lead_time = material.lead_time_weeks
        target_week = current_week + lead_time
        print(f"Lead time: {lead_time} hafta | Hedef hafta: {target_week}")
        
        # 3. İki tahmini de al
        chronos_forecast = None
        edi_forecast = None
        
        # Chronos tahmini
        if len(historical) >= 2:
            chronos_forecast = self.forecaster.forecast_single_week(historical, lead_time)
            print(f"Chronos tahmini: {chronos_forecast:.2f}")
            
            # Chronos tahminini kaydet
            self.edi_processor.save_chronos_forecast(
                material_id=material_id,
                forecast_week=current_week,
                target_week=target_week,
                forecast_value=chronos_forecast
            )
            # Hafızayı güncelle
            self.chronos_history = self.edi_processor.load_chronos_forecasts()
        else:
            print("Chronos tahmini yapılamadı (yetersiz veri)")
        
        # EDI tahmini (geçmiş tahminlerin ortalaması - tüm geçmiş haftalar)
        edi_forecast = self.edi_processor.get_edi_average_forecast(
            material_id, current_week, target_week
        )
        if edi_forecast:
            print(f"EDI tahmini (ortalama): {edi_forecast:.2f}")
        else:
            print("EDI tahmini bulunamadı")
        
        # 4. Performans karşılaştırması (son 3 hafta)
        chronos_rmse = self.edi_processor.calculate_source_accuracy(
            material_id, current_week, "chronos", lookback_weeks=3,
            chronos_history=self.chronos_history
        )
        edi_rmse = self.edi_processor.calculate_source_accuracy(
            material_id, current_week, "edi", lookback_weeks=3
        )
        
        print(f"\nPerformans Karşılaştırması (Son 3 Hafta RMSE):")
        print(f"  Chronos: {chronos_rmse:.2f}" if chronos_rmse else "  Chronos: Yeterli veri yok")
        print(f"  EDI: {edi_rmse:.2f}" if edi_rmse else "  EDI: Yeterli veri yok")
        
        # 5. Kaynak seçimi ve final tahmin
        selected_source = "EDI"
        raw_forecast = edi_forecast if edi_forecast else 0
        
        if chronos_forecast is not None and edi_forecast is not None:
            if chronos_rmse is not None and edi_rmse is not None:
                # Her zaman ağırlıklı ortalama al
                selected_source = "HYBRID"
                # Ters ağırlıklandırma: Hatası düşük olan daha fazla ağırlık alır
                w_chronos = 1.0 / (chronos_rmse + 1e-6)
                w_edi = 1.0 / (edi_rmse + 1e-6)
                total_weight = w_chronos + w_edi
                raw_forecast = (chronos_forecast * w_chronos + edi_forecast * w_edi) / total_weight
                
                # Performans farkını göster
                diff_percent = abs(chronos_rmse - edi_rmse) / max(chronos_rmse, edi_rmse)
                better_source = "Chronos" if chronos_rmse < edi_rmse else "EDI"
                
                print(f"-> Karar: HYBRID (agirlikli ortalama) = {raw_forecast:.2f}")
                print(f"   Agirliklar: Chronos={w_chronos/total_weight:.2%}, EDI={w_edi/total_weight:.2%}")
                print(f"   En iyi performans: {better_source} (Fark: {diff_percent:.1%})")
            elif chronos_rmse is not None:
                selected_source = "CHRONOS"
                raw_forecast = chronos_forecast
                print(f"-> Karar: CHRONOS secildi (EDI performansi bilinmiyor)")
            elif edi_rmse is not None:
                selected_source = "EDI"
                raw_forecast = edi_forecast
                print(f"-> Karar: EDI secildi (Chronos performansi bilinmiyor)")
            else:
                # Ilk haftalar: Basit ortalama
                selected_source = "HYBRID"
                raw_forecast = (chronos_forecast + edi_forecast) / 2
                print(f"-> Karar: HYBRID (basit ortalama, performans verileri henuz yok)")
        elif chronos_forecast is not None:
            selected_source = "CHRONOS"
            raw_forecast = chronos_forecast
            print(f"-> Karar: CHRONOS secildi (EDI tahmini yok)")
        elif edi_forecast is not None:
            selected_source = "EDI"
            raw_forecast = edi_forecast
            print(f"-> Karar: EDI secildi (Chronos tahmini yok)")
        else:
            print(f"-> UYARI: Hicbir tahmin bulunamadi, varsayilan deger kullaniliyor")
            raw_forecast = 0
        
        # 6. Horizon bazlı hata metriklerini al (bias düzeltmesi için)
        horizon_error = self.get_horizon_error(material_id, lead_time)
        if horizon_error:
            print(f"\nHorizon {lead_time} hata metrikleri:")
            print(f"  Bias: {horizon_error.bias:.2f}")
            print(f"  RMSE: {horizon_error.rmse:.2f}")
            print(f"  Std: {horizon_error.std:.2f}")
        else:
            print("\nHorizon hata metrikleri bulunamadı, varsayılan değerler kullanılacak.")
        
        # 7. Stok kararı oluştur
        decision = self.stock_calculator.make_stock_decision(
            material=material,
            current_week=current_week,
            raw_forecast=raw_forecast,
            horizon_error=horizon_error
        )
        
        # Hibrit sistem bilgilerini ekle
        decision.selected_source = selected_source
        decision.chronos_raw_forecast = chronos_forecast
        decision.edi_raw_forecast = edi_forecast
        
        # 8. Sonuçları yazdır
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
