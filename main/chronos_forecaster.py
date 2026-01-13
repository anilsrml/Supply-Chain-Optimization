"""
Chronos Model Entegrasyonu
Amazon Chronos foundation model ile talep tahmini
"""

import torch
import numpy as np
from typing import List, Optional, Tuple
from chronos import ChronosPipeline


class ChronosForecaster:
    """Chronos model ile talep tahmini yapan sınıf"""
    
    def __init__(self, model_size: str = "base"):
        """
        Chronos modelini başlatır.
        
        Args:
            model_size: Model boyutu - "tiny", "mini", "small", "base", "large"
        """
        self.model_name = f"amazon/chronos-t5-{model_size}"
        self.pipeline = None
        self._load_model()
    
    def _load_model(self):
        """Modeli yükler"""
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.pipeline = ChronosPipeline.from_pretrained(
            self.model_name,
            device_map=device,
            torch_dtype=torch.float32
        )
        print(f"Chronos model yüklendi: {self.model_name} ({device})")
    
    def forecast(
        self,
        historical_data: List[float],
        prediction_horizon: int,
        num_samples: int = 20
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Talep tahmini yapar.
        
        Args:
            historical_data: Geçmiş tüketim verileri
            prediction_horizon: Kaç hafta ileri tahmin yapılacak
            num_samples: Monte Carlo örnek sayısı
            
        Returns:
            Tuple of (mean_forecast, low_quantile, high_quantile)
        """
        if len(historical_data) < 2:
            raise ValueError("En az 2 geçmiş veri noktası gerekli")
        
        # Veriyi tensor'a çevir
        context = torch.tensor(historical_data, dtype=torch.float32)
        
        # Tahmin yap
        forecast_samples = self.pipeline.predict(
            context,
            prediction_length=prediction_horizon,
            num_samples=num_samples
        )
        
        # Numpy'a çevir
        samples = forecast_samples.numpy()
        
        # Ortalama ve quantile hesapla
        mean_forecast = np.median(samples, axis=1).flatten()
        low_quantile = np.quantile(samples, 0.1, axis=1).flatten()
        high_quantile = np.quantile(samples, 0.9, axis=1).flatten()
        
        return mean_forecast, low_quantile, high_quantile
    
    def forecast_single_week(
        self,
        historical_data: List[float],
        target_horizon: int
    ) -> float:
        """
        Belirli bir horizon için tek hafta tahmini yapar.
        
        Args:
            historical_data: Geçmiş tüketim verileri
            target_horizon: Hedef horizon (kaç hafta ileri)
            
        Returns:
            Tahmin edilen değer (ortalama)
        """
        if target_horizon < 1:
            raise ValueError("Target horizon en az 1 olmalı")
            
        mean_forecast, _, _ = self.forecast(historical_data, target_horizon)
        
        # Son hafta tahmini (hedef horizon)
        return float(mean_forecast[target_horizon - 1])
    
    def forecast_lead_time_demand(
        self,
        historical_data: List[float],
        lead_time_weeks: int
    ) -> Tuple[float, np.ndarray]:
        """
        Lead time boyunca toplam talep tahmini yapar.
        
        Args:
            historical_data: Geçmiş tüketim verileri
            lead_time_weeks: Lead time süresi (hafta)
            
        Returns:
            Tuple of (total_demand, weekly_forecasts)
        """
        mean_forecast, _, _ = self.forecast(historical_data, lead_time_weeks)
        total_demand = float(np.sum(mean_forecast))
        
        return total_demand, mean_forecast
