"""
EDI Veri İşleme Modülü
Haftalık EDI tahminlerini işler ve analiz eder
"""

import pandas as pd
import numpy as np
import json
import os
from typing import Dict, List, Optional, Tuple
from models import EDIForecast, ActualConsumption, MaterialData, ChronosForecastLog


def _load_excel_edi_dataframe(filepath: str, material_id: str):
    from excel_data_loader import ExcelDataLoader

    return ExcelDataLoader.build_edi_dataframe(filepath, material_id)


class EDIProcessor:
    """EDI tahmin verilerini işleyen sınıf"""
    
    def __init__(self):
        self.materials: Dict[str, MaterialData] = {}
    
    def load_from_dataframe(
        self,
        df: pd.DataFrame,
        material_id: str,
        lead_time_weeks: int,
    ) -> MaterialData:
        """
        DataFrame'den EDI verilerini yükler.

        DataFrame formatı:
        - Satırlar: Tahmin yapılan hafta (forecast_week)
        - Sütunlar: Tahmin edilen hafta (target_week)
        - Üst üçgen (tw > fw): EDI tahminleri
        - Köşegenin bir altı (fw == tw + 1): Gerçekleşen tüketim (hafta = tw)
        - Köşegen (tw == fw): Bu akışta gerçekleşen sayılmaz (yoksayılır)

        Args:
            df: EDI tahmin matrisi DataFrame
            material_id: Malzeme ID
            lead_time_weeks: Tedarik süresi
        """
        edi_forecasts = []
        actual_consumptions = []
        
        # DataFrame'i işle
        zero_count = 0
        for forecast_week in df.index:
            for target_week in df.columns:
                try:
                    fw = int(forecast_week)
                    tw = int(target_week)
                    value = df.loc[forecast_week, target_week]
                    
                    # NaN değerleri atla
                    if pd.isna(value):
                        continue
                    
                    # SIFIR MASKELEME: 0 değerleri veri olarak kabul etme
                    if float(value) == 0:
                        zero_count += 1
                        continue
                    
                    # Üst üçgen: Tahminler (target_week > forecast_week)
                    if tw > fw:
                        edi_forecasts.append(EDIForecast(
                            forecast_week=fw,
                            target_week=tw,
                            quantity=float(value)
                        ))
                    # Köşegenin hemen altı (aynı hedef hafta sütunu, bir sonraki tahmin satırı): gerçekleşen
                    elif fw == tw + 1:
                        actual_consumptions.append(ActualConsumption(
                            week=tw,
                            quantity=float(value)
                        ))
                except (ValueError, TypeError):
                    continue
        
        # Sıfır maskeleme logu
        if zero_count > 0:
            print(f"UYARI [{material_id}]: {zero_count} adet sıfır değer tespit edildi ve maskelendi.")
        
        material = MaterialData(
            material_id=material_id,
            lead_time_weeks=lead_time_weeks,
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
    ) -> MaterialData:
        """CSV dosyasından EDI verilerini yükler"""
        df = pd.read_csv(filepath, index_col=0)
        return self.load_from_dataframe(df, material_id, lead_time_weeks)

    def load_from_excel(
        self,
        filepath: str,
        material_id: str,
        lead_time_weeks: int,
    ) -> MaterialData:
        """data_safety_stock.xlsx tipi Excel dosyasından EDI matrisi yükler (sonra load_from_dataframe)."""
        df = _load_excel_edi_dataframe(filepath, material_id)
        return self.load_from_dataframe(df, material_id, lead_time_weeks)
    
    def get_historical_series(
        self,
        material_id: str,
        up_to_week: Optional[int] = None,
        exclude_zeros: bool = True
    ) -> List[float]:
        """
        Belirli bir haftaya kadar gerçekleşen tüketim serisini döner.
        
        Args:
            material_id: Malzeme ID
            up_to_week: Bu haftaya kadar (dahil)
            exclude_zeros: True ise sıfır değerler maskelenir (varsayılan)
            
        Returns:
            Kronolojik sırayla tüketim listesi (sıfırlar hariç)
        """
        material = self.materials.get(material_id)
        if not material:
            raise ValueError(f"Malzeme bulunamadı: {material_id}")
        
        actuals = material.get_actuals_dict()
        
        if up_to_week:
            actuals = {k: v for k, v in actuals.items() if k <= up_to_week}
        
        # SIFIR MASKELEME: Sıfır değerleri filtrele
        if exclude_zeros:
            original_count = len(actuals)
            actuals = {k: v for k, v in actuals.items() if v != 0}
            zero_count = original_count - len(actuals)
            if zero_count > 0:
                print(f"UYARI [{material_id}]: {zero_count} adet sıfır gerçekleşen değer maskelendi.")
        
        # Kronolojik sırala
        sorted_weeks = sorted(actuals.keys())
        return [actuals[w] for w in sorted_weeks]
    
    def get_target_week_column(
        self,
        material_id: str,
        target_week: int,
        up_to_week: int,
        exclude_zeros: bool = True
    ) -> List[float]:
        """
        Hedef haftanın sütun verisini döner: o haftaya yapılmış EDI tahminleri.

        EDI matrisinde target_week sütunundaki değerleri fw=1..up_to_week
        arasında kronolojik sırayla toplar. Chronos'a girdi olarak
        tahminlerin yakınsama trendini verir.

        Args:
            material_id: Malzeme ID
            target_week: Hedef hafta (sütun)
            up_to_week: Bu haftaya kadar olan tahminler (dahil)
            exclude_zeros: True ise sıfır değerler maskelenir

        Returns:
            Kronolojik sırayla tahmin listesi (boşluklar/sıfırlar hariç)
        """
        material = self.materials.get(material_id)
        if not material:
            raise ValueError(f"Malzeme bulunamadı: {material_id}")

        matrix = material.get_forecast_matrix()

        values = []
        zero_count = 0
        for fw in range(1, up_to_week + 1):
            if fw in matrix and target_week in matrix[fw]:
                value = matrix[fw][target_week]
                if exclude_zeros and value == 0:
                    zero_count += 1
                    continue
                values.append(value)

        if zero_count > 0:
            print(
                f"UYARI [{material_id}]: Hedef hafta {target_week} sütununda "
                f"{zero_count} adet sıfır değer maskelendi."
            )

        return values

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
        max_horizon: int = 12,
        current_week: Optional[int] = None
    ) -> Dict[int, Dict[str, float]]:
        """
        Her horizon için tahmin hatalarını hesaplar.
        
        ÖNEMLİ: Look-ahead bias'ı engellemek için sadece current_week'e kadar
        olan gerçekleşen veriler kullanılır!
        
        Args:
            material_id: Malzeme ID
            max_horizon: Maksimum horizon değeri
            current_week: Mevcut hafta (None ise tüm veriler kullanılır)
        
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
                
                # LOOK-AHEAD BIAS ENGELLENİYOR:
                # Current week belirtilmişse, sadece o haftaya kadar olan gerçekleşenleri kullan
                if current_week is not None and target_week > current_week:
                    continue
                
                # SIFIR MASKELEME: Tahmin sıfırsa atla
                if forecast_qty == 0:
                    continue
                
                # Gerçekleşen değer var mı?
                if target_week in actuals:
                    actual_qty = actuals[target_week]
                    # SIFIR MASKELEME: Gerçekleşen sıfırsa atla
                    if actual_qty == 0:
                        continue
                    error = forecast_qty - actual_qty
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
    
    def save_chronos_forecast(
        self,
        material_id: str,
        forecast_week: int,
        target_week: int,
        forecast_value: Optional[float],
        filepath: str = "chronos_forecasts.json"
    ):
        """
        Chronos tahminini JSON dosyasına kaydeder.
        
        Args:
            material_id: Malzeme ID
            forecast_week: Tahminin yapıldığı hafta
            target_week: Tahmin edilen hafta
            forecast_value: Tahmin değeri
            filepath: JSON dosya yolu
        """
        # None / NaN gibi geçersiz değerleri kaydetme (sonradan RMSE hesaplarını bozar)
        if forecast_value is None:
            print(
                f"UYARI [{material_id}]: Chronos tahmini None geldi (fw={forecast_week}, tw={target_week}). "
                f"JSON'a kaydedilmiyor."
            )
            return
        try:
            forecast_value = float(forecast_value)
        except (TypeError, ValueError):
            print(
                f"UYARI [{material_id}]: Chronos tahmini sayıya çevrilemedi (fw={forecast_week}, tw={target_week}). "
                f"JSON'a kaydedilmiyor."
            )
            return
        if np.isnan(forecast_value):
            print(
                f"UYARI [{material_id}]: Chronos tahmini NaN geldi (fw={forecast_week}, tw={target_week}). "
                f"JSON'a kaydedilmiyor."
            )
            return

        # Mevcut verileri yükle
        data = {}
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except:
                data = {}
        
        # Yeni tahmini ekle
        if material_id not in data:
            data[material_id] = []
        
        log_entry = {
            'forecast_week': forecast_week,
            'target_week': target_week,
            'forecast_value': forecast_value,
            'timestamp': ChronosForecastLog(
                material_id=material_id,
                forecast_week=forecast_week,
                target_week=target_week,
                forecast_value=forecast_value
            ).timestamp
        }
        
        data[material_id].append(log_entry)
        
        # Dosyaya kaydet
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load_chronos_forecasts(
        self,
        filepath: str = "chronos_forecasts.json"
    ) -> Dict[str, List[ChronosForecastLog]]:
        """
        Chronos tahmin geçmişini JSON dosyasından yükler.
        
        Args:
            filepath: JSON dosya yolu
            
        Returns:
            {material_id: [ChronosForecastLog, ...]}
        """
        if not os.path.exists(filepath):
            return {}
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            result = {}
            invalid_found = False
            for material_id, logs in data.items():
                cleaned_logs: List[ChronosForecastLog] = []
                for log in logs:
                    fv = log.get('forecast_value', None)
                    if fv is None:
                        invalid_found = True
                        continue
                    try:
                        fv = float(fv)
                    except (TypeError, ValueError):
                        invalid_found = True
                        continue
                    if np.isnan(fv):
                        invalid_found = True
                        continue

                    cleaned_logs.append(
                        ChronosForecastLog(
                            material_id=material_id,
                            forecast_week=log['forecast_week'],
                            target_week=log['target_week'],
                            forecast_value=fv,
                            timestamp=log.get('timestamp', '')
                        )
                    )

                if cleaned_logs:
                    result[material_id] = cleaned_logs
            
            # İsteğe bağlı otomatik temizlik: bozuk kayıtlar varsa dosyayı yeniden yaz
            # (Bu sayede bir sonraki çalıştırmada da aynı problem tekrarlanmaz.)
            if invalid_found:
                try:
                    serializable = {}
                    for mid, logs in result.items():
                        serializable[mid] = [
                            {
                                "forecast_week": l.forecast_week,
                                "target_week": l.target_week,
                                "forecast_value": l.forecast_value,
                                "timestamp": l.timestamp,
                            }
                            for l in logs
                        ]
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(serializable, f, indent=2, ensure_ascii=False)
                except Exception:
                    # Temizlik yazımı başarısız olursa ana akışı bozma
                    pass

            return result
        except:
            return {}
    
    def get_edi_average_forecast(
        self,
        material_id: str,
        current_week: int,
        target_week: int,
        lookback_weeks: Optional[int] = None,
    ) -> Optional[float]:
        """
        Hedef hafta için geçmişte yapılmış EDI tahminlerinin ortalamasını döner.
        Yöntem: IQR ile aykırı değerleri temizle, sonra aritmetik ortalama al.

        Args:
            material_id: Malzeme ID
            current_week: Mevcut hafta
            target_week: Hedef hafta
            lookback_weeks: Kaç hafta geriye bakılacak (None ise lead_time kadar geri gider)

        Returns:
            EDI tahminlerinin hesaplanmış değeri (veya None)
        """
        material = self.materials.get(material_id)
        if not material:
            return None

        # lookback_weeks belirtilmemişse, lead_time kadar geri git
        if lookback_weeks is None:
            lookback_weeks = material.lead_time_weeks

        matrix = material.get_forecast_matrix()

        # Geçmiş haftalardaki tahminleri topla (Hafta 1'den current_week'e kadar)
        forecasts = []
        zero_count = 0
        for week in range(max(1, current_week - lookback_weeks), current_week + 1):
            if week in matrix and target_week in matrix[week]:
                value = matrix[week][target_week]
                # SIFIR MASKELEME: 0 değerleri hesaba katma
                if value == 0:
                    zero_count += 1
                    continue
                forecasts.append(value)

        if not forecasts:
            # Hiç tahmin yoksa, en son bulunan tahmini kullan (sıfır olmayanlardan)
            for week in range(current_week, 0, -1):
                if week in matrix and target_week in matrix[week]:
                    value = matrix[week][target_week]
                    if value != 0:
                        return value
            # Tüm değerler sıfırsa veya hiç veri yoksa
            if zero_count > 0:
                print(f"UYARI [{material_id}]: Hedef hafta {target_week} için tüm EDI tahminleri sıfır. 'Veri Yok' döndürülüyor.")
            return None

        # IQR ile aykırı değerleri temizle, ardından aritmetik ortalama al
        original_forecasts = list(forecasts)
        forecasts = self._remove_outliers_iqr(forecasts)

        # Temizleme sonrası veri kalmadıysa, orijinal verinin medyanını kullan
        if not forecasts:
            return float(np.median(original_forecasts))

        return float(np.mean(forecasts))
    
    def _remove_outliers_iqr(
        self,
        data: List[float],
        iqr_multiplier: float = 1.5
    ) -> List[float]:
        """
        IQR (Interquartile Range) yöntemiyle aykırı değerleri temizler.
        
        Args:
            data: Veri listesi
            iqr_multiplier: IQR çarpanı (varsayılan 1.5, standart değer)
            
        Returns:
            Aykırı değerlerden temizlenmiş veri listesi
        """
        if len(data) < 4:  # IQR hesabı için en az 4 veri noktası gerekli
            return data
        
        data_arr = np.array(data)
        
        # Q1 (25. persentil) ve Q3 (75. persentil) hesapla
        q1 = np.percentile(data_arr, 25)
        q3 = np.percentile(data_arr, 75)
        
        # IQR hesapla
        iqr = q3 - q1
        
        # Alt ve üst sınırları belirle
        lower_bound = q1 - iqr_multiplier * iqr
        upper_bound = q3 + iqr_multiplier * iqr
        
        # Aykırı olmayan değerleri filtrele
        filtered_data = [x for x in data if lower_bound <= x <= upper_bound]
        
        # Eğer tüm veriler temizlendiyse, orijinal veriyi döndür
        if not filtered_data:
            return data
        
        return filtered_data
    
    def calculate_source_accuracy(
        self,
        material_id: str,
        current_week: int,
        source: str,
        lookback_weeks: Optional[int] = None,
        chronos_history: Optional[Dict[str, List[ChronosForecastLog]]] = None
    ) -> Optional[float]:
        """
        Belirli bir kaynak icin son N haftanin RMSE'sini hesaplar.
        
        ONEMLI: Sadece current_week'ten ONCEKI gerceklesmis veriler kullanilir!
        Target_week >= current_week olan tahminler degerlendirilemez.
        
        CHRONOS icin:
            - Son lead_time haftada yapilan tahminler
            - Sadece target_week < current_week olan tahminler
        
        EDI icin:
            - Son lead_time haftanin gerceklesenleri
            - Her hafta icin o haftaya yapilan son 2 tahmin (horizon-1 ve horizon-2)
        
        Args:
            material_id: Malzeme ID
            current_week: Mevcut hafta
            source: "chronos" veya "edi"
            lookback_weeks: Kac hafta geriye bakilacak (None ise lead_time kullanilir)
            chronos_history: Chronos tahmin gecmisi (source="chronos" icin gerekli)
            
        Returns:
            RMSE degeri (veya None)
        """
        material = self.materials.get(material_id)
        if not material:
            return None
        
        # lookback_weeks belirtilmemisse lead_time kullan
        if lookback_weeks is None:
            lookback_weeks = material.lead_time_weeks
        
        actuals = material.get_actuals_dict()
        errors = []
        
        if source == "chronos":
            # CHRONOS: Son N haftanin gerceklesenleri icin Chronos tahminlerini degerlendir
            # EDI ile ayni mantik: target_week bazli bakilir
            if not chronos_history or material_id not in chronos_history:
                return None
            
            logs = chronos_history[material_id]
            
            # Son N haftanin gerceklesen degerlerini al (current_week'ten once)
            for target_week in range(max(1, current_week - lookback_weeks), current_week):
                if target_week not in actuals:
                    continue
                
                actual_value = actuals[target_week]
                # SIFIR MASKELEME: Gerçekleşen sıfırsa atla
                if actual_value == 0:
                    continue
                
                # Bu haftaya yapilmis Chronos tahminlerini bul
                target_forecasts = [log for log in logs 
                                   if log.target_week == target_week and log.forecast_week < target_week]
                
                for log in target_forecasts:
                    # Bozuk/eksik kayıtları atla
                    if log.forecast_value is None:
                        continue
                    # SIFIR MASKELEME: Tahmin sıfırsa atla
                    if log.forecast_value == 0:
                        continue
                    error = log.forecast_value - actual_value
                    errors.append(error)
        
        elif source == "edi":
            # EDI: Son N haftanin gerceklesenleri icin, her birine yapilan 2 tahmini degerlendir
            matrix = material.get_forecast_matrix()
            
            # Son N haftanin gerceklesen degerlerini al
            for target_week in range(max(1, current_week - lookback_weeks), current_week):
                if target_week not in actuals:
                    continue
                
                actual_value = actuals[target_week]
                # SIFIR MASKELEME: Gerçekleşen sıfırsa atla
                if actual_value == 0:
                    continue
                
                # Bu haftaya yapilan son 2 tahmini bul (horizon-1 ve horizon-2)
                # Horizon-1: target_week - 1'den yapilan tahmin
                # Horizon-2: target_week - 2'den yapilan tahmin
                for horizon in [1, 2]:
                    forecast_week = target_week - horizon
                    if forecast_week >= 1 and forecast_week in matrix:
                        if target_week in matrix[forecast_week]:
                            forecast = matrix[forecast_week][target_week]
                            # SIFIR MASKELEME: Tahmin sıfırsa atla
                            if forecast == 0:
                                continue
                            error = forecast - actual_value
                            errors.append(error)
        
        if len(errors) < 1:
            return None
        
        # RMSE hesapla (en az 1 veri noktasi yeterli)
        errors_arr = np.array(errors)
        rmse = float(np.sqrt(np.mean(errors_arr ** 2)))
        
        return rmse