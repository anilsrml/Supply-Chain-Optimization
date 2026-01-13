"""
EDI Veri İşleme Modülü
Haftalık EDI tahminlerini işler ve analiz eder
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from models import EDIForecast, ActualConsumption, MaterialData


class EDIProcessor:
    """EDI tahmin verilerini işleyen sınıf"""
    
    def __init__(self):
        self.materials: Dict[str, MaterialData] = {}
    
    def load_from_dataframe(
        self,
        df: pd.DataFrame,
        material_id: str,
        lead_time_weeks: int,
        current_stock: float,
        service_level: float = 0.95
    ) -> MaterialData:
        """
        DataFrame'den EDI verilerini yükler.
        
        DataFrame formatı (üst üçgen matris):
        - Satırlar: Tahmin yapılan hafta (forecast_week)
        - Sütunlar: Tahmin edilen hafta (target_week) 
        - Değerler: Tahmin miktarları
        - Alt üçgen: Gerçekleşen değerler (actual)
        
        Args:
            df: EDI tahmin matrisi DataFrame
            material_id: Malzeme ID
            lead_time_weeks: Tedarik süresi
            current_stock: Mevcut stok
            service_level: Servis seviyesi
        """
        edi_forecasts = []
        actual_consumptions = []
        
        # DataFrame'i işle
        for forecast_week in df.index:
            for target_week in df.columns:
                try:
                    fw = int(forecast_week)
                    tw = int(target_week)
                    value = df.loc[forecast_week, target_week]
                    
                    if pd.isna(value):
                        continue
                    
                    # Üst üçgen: Tahminler (target_week > forecast_week)
                    if tw > fw:
                        edi_forecasts.append(EDIForecast(
                            forecast_week=fw,
                            target_week=tw,
                            quantity=float(value)
                        ))
                    # Diagonal: Gerçekleşen değerler
                    elif tw == fw:
                        actual_consumptions.append(ActualConsumption(
                            week=tw,
                            quantity=float(value)
                        ))
                except (ValueError, TypeError):
                    continue
        
        material = MaterialData(
            material_id=material_id,
            lead_time_weeks=lead_time_weeks,
            current_stock=current_stock,
            service_level=service_level,
            edi_forecasts=edi_forecasts,
            actual_consumptions=actual_consumptions
        )
        
        self.materials[material_id] = material
        return material
    
    def load_from_csv(
        self,
        filepath: str,
        material_id: str,
        lead_time_weeks: int,
        current_stock: float,
        service_level: float = 0.95
    ) -> MaterialData:
        """CSV dosyasından EDI verilerini yükler"""
        df = pd.read_csv(filepath, index_col=0)
        return self.load_from_dataframe(
            df, material_id, lead_time_weeks, current_stock, service_level
        )
    
    def get_historical_series(
        self,
        material_id: str,
        up_to_week: Optional[int] = None
    ) -> List[float]:
        """
        Belirli bir haftaya kadar gerçekleşen tüketim serisini döner.
        
        Args:
            material_id: Malzeme ID
            up_to_week: Bu haftaya kadar (dahil)
            
        Returns:
            Kronolojik sırayla tüketim listesi
        """
        material = self.materials.get(material_id)
        if not material:
            raise ValueError(f"Malzeme bulunamadı: {material_id}")
        
        actuals = material.get_actuals_dict()
        
        if up_to_week:
            actuals = {k: v for k, v in actuals.items() if k <= up_to_week}
        
        # Kronolojik sırala
        sorted_weeks = sorted(actuals.keys())
        return [actuals[w] for w in sorted_weeks]
    
    def get_forecast_for_horizon(
        self,
        material_id: str,
        forecast_week: int,
        target_week: int
    ) -> Optional[float]:
        """Belirli bir hafta ve horizon için EDI tahminini döner"""
        material = self.materials.get(material_id)
        if not material:
            return None
        
        matrix = material.get_forecast_matrix()
        return matrix.get(forecast_week, {}).get(target_week)
    
    def get_latest_forecasts(
        self,
        material_id: str,
        current_week: int
    ) -> Dict[int, float]:
        """
        Mevcut haftadan ileri haftalar için en son tahminleri döner.
        
        Returns:
            {target_week: forecast_quantity}
        """
        material = self.materials.get(material_id)
        if not material:
            return {}
        
        matrix = material.get_forecast_matrix()
        
        # Mevcut haftanın tahminlerini al
        if current_week in matrix:
            return {
                tw: qty for tw, qty in matrix[current_week].items()
                if tw > current_week
            }
        
        # En yakın önceki haftanın tahminlerini kullan
        past_weeks = [w for w in matrix.keys() if w <= current_week]
        if past_weeks:
            latest_week = max(past_weeks)
            return {
                tw: qty for tw, qty in matrix[latest_week].items()
                if tw > current_week
            }
        
        return {}
    
    def calculate_forecast_errors(
        self,
        material_id: str,
        max_horizon: int = 12
    ) -> Dict[int, Dict[str, float]]:
        """
        Her horizon için tahmin hatalarını hesaplar.
        
        Returns:
            {horizon: {'bias': float, 'rmse': float, 'std': float, 'count': int}}
        """
        material = self.materials.get(material_id)
        if not material:
            return {}
        
        actuals = material.get_actuals_dict()
        matrix = material.get_forecast_matrix()
        
        # Her horizon için hataları topla
        horizon_errors: Dict[int, List[float]] = {h: [] for h in range(1, max_horizon + 1)}
        
        for forecast_week, forecasts in matrix.items():
            for target_week, forecast_qty in forecasts.items():
                horizon = target_week - forecast_week
                
                if horizon < 1 or horizon > max_horizon:
                    continue
                
                # Gerçekleşen değer var mı?
                if target_week in actuals:
                    error = forecast_qty - actuals[target_week]
                    horizon_errors[horizon].append(error)
        
        # Metrikleri hesapla
        results = {}
        for horizon, errors in horizon_errors.items():
            if len(errors) >= 2:  # En az 2 veri noktası
                errors_arr = np.array(errors)
                results[horizon] = {
                    'bias': float(np.mean(errors_arr)),
                    'rmse': float(np.sqrt(np.mean(errors_arr ** 2))),
                    'std': float(np.std(errors_arr, ddof=1)),
                    'count': len(errors)
                }
        
        return results
