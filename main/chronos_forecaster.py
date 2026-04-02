"""
Chronos Model Entegrasyonu
Amazon Chronos foundation model ile talep tahmini
"""

import torch
import numpy as np
from typing import List, Optional, Tuple


# Bolt modelleri için geçerli boyutlar
_BOLT_SIZES = {"bolt-tiny", "bolt-mini", "bolt-small", "bolt-base"}
# T5 modelleri için geçerli boyutlar
_T5_SIZES = {"tiny", "mini", "small", "base", "large"}


class ChronosForecaster:
    """Chronos model ile talep tahmini yapan sınıf"""

    def __init__(self, model_size: str = "bolt-base"):
        """
        Chronos modelini başlatır.

        Args:
            model_size: Model boyutu
                Bolt (önerilen): "bolt-tiny", "bolt-mini", "bolt-small", "bolt-base"
                T5 (eski nesil): "tiny", "mini", "small", "base", "large"
        """
        if model_size in _BOLT_SIZES:
            self.model_name = f"amazon/chronos-{model_size}"
            self._is_bolt = True
        elif model_size in _T5_SIZES:
            self.model_name = f"amazon/chronos-t5-{model_size}"
            self._is_bolt = False
        else:
            raise ValueError(
                f"Geçersiz model_size: '{model_size}'. "
                f"Bolt: {sorted(_BOLT_SIZES)}, T5: {sorted(_T5_SIZES)}"
            )
        self.pipeline = None
        self._load_model()

    def _load_model(self):
        """Modeli yükler"""
        device = "cuda" if torch.cuda.is_available() else "cpu"
        if self._is_bolt:
            from chronos import ChronosBoltPipeline
            self.pipeline = ChronosBoltPipeline.from_pretrained(
                self.model_name,
                device_map=device,
                torch_dtype=torch.float32
            )
        else:
            from chronos import ChronosPipeline
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
            num_samples: Monte Carlo örnek sayısı (yalnızca T5 modelleri için kullanılır)

        Returns:
            Tuple of (mean_forecast, low_quantile, high_quantile)
        """
        if len(historical_data) < 2:
            raise ValueError("En az 2 geçmiş veri noktası gerekli")

        context = torch.tensor(historical_data, dtype=torch.float32)

        if self._is_bolt:
            # Bolt: doğrudan quantile tahmini (sampling yok)
            quantile_forecasts, mean_forecasts = self.pipeline.predict_quantiles(
                context,
                prediction_length=prediction_horizon,
                quantile_levels=[0.1, 0.5, 0.9],
            )
            mean_forecast = mean_forecasts[0].numpy().flatten()
            low_quantile = quantile_forecasts[0, :, 0].numpy().flatten()
            high_quantile = quantile_forecasts[0, :, 2].numpy().flatten()
        else:
            # T5: sample tabanlı tahmin
            forecast_samples = self.pipeline.predict(
                context,
                prediction_length=prediction_horizon,
                num_samples=num_samples
            )
            samples = forecast_samples.numpy()
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
