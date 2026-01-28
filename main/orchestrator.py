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
    Dinamik Stok Planlama Sistemi Orkestratörü (Gerçek Zamanlı Chronos)
    
    Haftalık çalışma akışı (Rolling Forecast):
    1. Geçmiş veriyi kullanarak Chronos ile gerçek zamanlı tahmin
    2. EDI tahminlerini geçmişten topla ve hesapla
    3. Her iki kaynağın performansını değerlendir (son 3 hafta RMSE)
    4. Hibrit tahmin oluştur (performansa göre ağırlıklı ortalama)
    5. Horizon bazlı bias düzeltmesi uygula
    6. Emniyet stoğu ve reorder point hesapla
    7. Sipariş kararı ver
    
    ÖNEMLİ: Sadece mevcut haftaya kadar olan geçmiş veri kullanılır.
    Gelecek bilgisi sızması (look-ahead bias) engellenir.
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
        
        # Chronos tahmin geçmişini yükle
        # Not: Bu geçmiş, gerçek zamanlı yapılan tahminlerin kayıtlarını içerir
        # Performans karşılaştırması için kullanılır
        self.chronos_history = self.edi_processor.load_chronos_forecasts()
        
        print("Stok Planlama Sistemi başlatıldı (Gerçek Zamanlı Chronos - Hibrit Mod).")
    
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
    
    def _update_horizon_errors(self, material_id: str, current_week: Optional[int] = None):
        """
        Horizon bazlı hataları günceller.
        
        Args:
            material_id: Malzeme ID
            current_week: Mevcut hafta (None ise tüm veriler kullanılır)
        """
        error_dict = self.edi_processor.calculate_forecast_errors(
            material_id, 
            current_week=current_week
        )
        
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
    
    def backfill_chronos_forecasts(
        self,
        material_id: str,
        current_week: int
    ):
        """
        Geçmiş haftalar için geriye dönük Chronos tahminleri üretir.
        
        ÖNEMLİ: 
        - Chronos HER ZAMAN sadece 1 hafta sonrasını tahmin eder
        - Lead_time'dan bağımsız olarak horizon=1 kullanılır
        - Look-ahead bias engellenir! Her hafta için sadece o haftaya kadar olan geçmiş veri kullanılır
        
        Örnek (current_week=4):
        - Hafta 1 verisi ile → Hafta 2 tahmini (horizon=1)
        - Hafta 1-2 verisi ile → Hafta 3 tahmini (horizon=1)
        - Hafta 1-2-3 verisi ile → Hafta 4 tahmini (horizon=1)
        
        Args:
            material_id: Malzeme ID
            current_week: Mevcut hafta
        """
        print(f"\n[BACKFILL] Gecmis haftalar icin Chronos tahminleri uretiliyor (horizon=1)...")
        
        backfilled_count = 0
        skipped_count = 0
        
        # Hafta 1'den current_week'e kadar tüm geçmiş haftalar için tahmin yap
        # Her zaman 1 sonraki haftayı tahmin et
        for forecast_week in range(1, current_week):
            target_week = forecast_week + 1  # HER ZAMAN +1 (horizon=1)
            
            # Hedef hafta current_week'i geçemez (gelecek bilgisi kullanılmaz)
            if target_week > current_week:
                break
            
            # Bu tahmin zaten var mı kontrol et
            existing_forecasts = self.chronos_history.get(material_id, [])
            already_exists = any(
                log.forecast_week == forecast_week and log.target_week == target_week
                for log in existing_forecasts
            )
            
            if already_exists:
                skipped_count += 1
                continue
            
            # Geçmiş veriyi al (sadece forecast_week'e kadar)
            historical = self.edi_processor.get_historical_series(material_id, forecast_week)
            
            # En az 2 veri noktası gerekli
            if len(historical) < 2:
                continue
            
            try:
                # Chronos tahmini yap - HER ZAMAN horizon=1
                forecast_value = self.forecaster.forecast_single_week(historical, target_horizon=1)
                
                # Kaydet
                self.edi_processor.save_chronos_forecast(
                    material_id=material_id,
                    forecast_week=forecast_week,
                    target_week=target_week,
                    forecast_value=forecast_value
                )
                
                backfilled_count += 1
                print(f"  [+] Hafta {forecast_week} -> Hafta {target_week}: {forecast_value:.2f} (horizon=1)")
                
            except Exception as e:
                print(f"  [!] Hafta {forecast_week} -> Hafta {target_week}: HATA - {str(e)}")
        
        # Hafızayı güncelle
        if backfilled_count > 0:
            self.chronos_history = self.edi_processor.load_chronos_forecasts()
            print(f"\n[BACKFILL] Tamamlandı: {backfilled_count} yeni, {skipped_count} mevcut tahmin")
        else:
            print(f"[BACKFILL] Tüm geçmiş tahminler zaten mevcut ({skipped_count} tahmin)")
    
    def run_weekly_planning(
        self,
        material_id: str,
        current_week: int
    ) -> StockDecision:
        """
        Haftalık planlama döngüsünü çalıştırır (Gerçek Zamanlı Hibrit Sistem).
        
        ÇALIŞMA MANTĞI:
        1. Geçmiş haftalar için geriye dönük tahminler üret (backfill)
        2. Sadece current_week'e kadar olan geçmiş veri kullanılır
        3. Chronos gerçek zamanlı olarak iki tahmin üretir:
           - JSON/performans geçmişi için: sadece +1 hafta (horizon=1)
           - Karar/Hibrit için: lead time hedef haftası (horizon=lead_time)
        4. EDI tahminleri geçmişten toplanır
        5. Her iki kaynağın performansı değerlendirilir (backfill sayesinde yeterli veri)
        6. Performansa göre ağırlıklı hibrit tahmin oluşturulur
        
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
        
        # 0. Geçmiş haftalar için geriye dönük tahminler üret (ilk çalıştırmada)
        self.backfill_chronos_forecasts(material_id, current_week)
        
        # 1. Geçmiş tüketim serisini al
        historical = self.edi_processor.get_historical_series(material_id, current_week)
        print(f"\nGecmis veri sayisi: {len(historical)}")
        
        # 2. Lead time ve hedef hafta
        lead_time = material.lead_time_weeks
        target_week = current_week + lead_time
        print(f"Lead time: {lead_time} hafta | Hedef hafta: {target_week}")
        
        # 3. İki tahmini de al
        # - Chronos JSON kaydı (performans geçmişi) için SADECE horizon=1 tutulur.
        # - Karar/Hibrit hesap için ise lead time hedef haftasıyla aynı hedefi temsil edecek şekilde
        #   horizon=lead_time tahmini kullanılır.
        chronos_forecast = None  # karar/hybrid için: current_week + lead_time
        chronos_next_week_forecast = None  # sadece log/JSON için: current_week + 1
        edi_forecast = None
        
        # Chronos tahminleri
        if len(historical) >= 2:

            # 3.a) Log/performans için +1 hafta tahmini (horizon=1)
            chronos_next_week_forecast = self.forecaster.forecast_single_week(
                historical, target_horizon=1
            )

            
            # 3.b) Karar/Hibrit için lead time hedef haftası tahmini (horizon=lead_time)
            if lead_time >= 1:                          
                chronos_forecast = self.forecaster.forecast_single_week(historical, target_horizon=lead_time)
                print(f"Chronos tahmini (lead time hedef hafta): {chronos_forecast:.2f}")
            
            # Chronos tahminini kaydet
            # Not: Chronos current_week+1 için tahmin yapar (horizon=1)
            if chronos_next_week_forecast is not None:
                self.edi_processor.save_chronos_forecast(
                    material_id=material_id,
                    forecast_week=current_week,
                    target_week=current_week + 1,  # Chronos her zaman 1 hafta sonrasi
                    forecast_value=chronos_next_week_forecast
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
        # ÖNEMLİ: Bias hesaplamasını current_week ile sınırla (look-ahead bias engellenir)
        self._update_horizon_errors(material_id, current_week=current_week)
        
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
