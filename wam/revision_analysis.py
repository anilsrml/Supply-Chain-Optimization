"""
Revizyon analizi modülü.
Tahminlerin bias, hata varyansı ve revizyon oynaklığını hesaplar.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple


def calculate_bias(forecasts: Dict[str, float], actuals: pd.Series) -> float:
    """
    Tahminlerin ortalama sapmasını (bias) hesaplar.
    
    Bias = mean(Tahmin - Gerçek)
    - Pozitif: Tahminler gerçekten yüksek (iyimser)
    - Negatif: Tahminler gerçekten düşük (kötümser)
    
    Args:
        forecasts: {hedef_hafta: tahmin_değeri}
        actuals: Gerçekleşen değerler serisi
        
    Returns:
        float: Ortalama bias
    """
    errors = []
    for week, forecast in forecasts.items():
        if week in actuals.index:
            error = forecast - actuals[week]
            errors.append(error)
    
    if not errors:
        return np.nan
    
    return np.mean(errors)


def calculate_error_variance(forecasts: Dict[str, float], actuals: pd.Series) -> float:
    """
    Tahmin hatalarının varyansını hesaplar.
    
    Yüksek varyans = Tahminlerin tutarsız olduğunu gösterir
    
    Args:
        forecasts: {hedef_hafta: tahmin_değeri}
        actuals: Gerçekleşen değerler serisi
        
    Returns:
        float: Hata varyansı
    """
    errors = []
    for week, forecast in forecasts.items():
        if week in actuals.index:
            error = forecast - actuals[week]
            errors.append(error)
    
    if len(errors) < 2:
        return np.nan
    
    return np.var(errors, ddof=1)


def calculate_rmse(forecasts: Dict[str, float], actuals: pd.Series) -> float:
    """
    Root Mean Squared Error hesaplar.
    
    Args:
        forecasts: {hedef_hafta: tahmin_değeri}
        actuals: Gerçekleşen değerler serisi
        
    Returns:
        float: RMSE
    """
    squared_errors = []
    for week, forecast in forecasts.items():
        if week in actuals.index:
            error = forecast - actuals[week]
            squared_errors.append(error ** 2)
    
    if not squared_errors:
        return np.nan
    
    return np.sqrt(np.mean(squared_errors))


def calculate_mae(forecasts: Dict[str, float], actuals: pd.Series) -> float:
    """
    Mean Absolute Error hesaplar.
    
    Args:
        forecasts: {hedef_hafta: tahmin_değeri}
        actuals: Gerçekleşen değerler serisi
        
    Returns:
        float: MAE
    """
    abs_errors = []
    for week, forecast in forecasts.items():
        if week in actuals.index:
            error = abs(forecast - actuals[week])
            abs_errors.append(error)
    
    if not abs_errors:
        return np.nan
    
    return np.mean(abs_errors)


def calculate_revision_volatility(revision_pairs: Dict) -> Dict[int, Dict]:
    """
    Revizyon oynaklığını hesaplar.
    
    Her horizon için:
    - mean_revision: Ortalama revizyon
    - std_revision: Revizyon standart sapması
    - mean_abs_revision: Ortalama mutlak revizyon
    
    Args:
        revision_pairs: get_revision_pairs() çıktısı
        
    Returns:
        dict: {horizon: {metrikler}}
    """
    # Revizyonları horizon bazlı grupla
    revisions_by_horizon = {}
    
    for week, pairs in revision_pairs.items():
        for pair in pairs:
            horizon = pair['horizon']
            revision = pair['revision']
            
            if horizon not in revisions_by_horizon:
                revisions_by_horizon[horizon] = []
            revisions_by_horizon[horizon].append(revision)
    
    # Her horizon için metrikleri hesapla
    volatility_metrics = {}
    
    for horizon, revisions in sorted(revisions_by_horizon.items()):
        if len(revisions) < 2:
            continue
        
        revisions = np.array(revisions)
        volatility_metrics[horizon] = {
            'mean_revision': np.mean(revisions),
            'std_revision': np.std(revisions, ddof=1),
            'mean_abs_revision': np.mean(np.abs(revisions)),
            'count': len(revisions)
        }
    
    return volatility_metrics


def analyze_by_horizon(forecasts_by_horizon: Dict, actuals: pd.Series) -> pd.DataFrame:
    """
    Tüm hata metriklerini horizon bazlı hesaplar.
    
    Args:
        forecasts_by_horizon: extract_forecasts_by_horizon() çıktısı
        actuals: Gerçekleşen değerler
        
    Returns:
        DataFrame: Horizon bazlı hata metrikleri
    """
    results = []
    
    for horizon in sorted(forecasts_by_horizon.keys()):
        forecasts = forecasts_by_horizon[horizon]
        
        bias = calculate_bias(forecasts, actuals)
        variance = calculate_error_variance(forecasts, actuals)
        rmse = calculate_rmse(forecasts, actuals)
        mae = calculate_mae(forecasts, actuals)
        
        results.append({
            'Horizon': horizon,
            'Bias': bias,
            'Error_Variance': variance,
            'Error_Std': np.sqrt(variance) if not np.isnan(variance) else np.nan,
            'RMSE': rmse,
            'MAE': mae,
            'Sample_Size': len(forecasts)
        })
    
    return pd.DataFrame(results)


def generate_full_report(matrix: pd.DataFrame) -> str:
    """
    Tam analiz raporunu oluşturur.
    
    Args:
        matrix: Üçgen matris verisi
        
    Returns:
        str: Formatlı rapor
    """
    from data_loader import extract_actuals, extract_forecasts_by_horizon, get_revision_pairs
    
    # Verileri çıkar
    actuals = extract_actuals(matrix)
    forecasts_by_horizon = extract_forecasts_by_horizon(matrix)
    revision_pairs = get_revision_pairs(matrix)
    
    # Rapor oluştur
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("TAHMİN REVİZYON ANALİZİ RAPORU")
    report_lines.append("=" * 60)
    
    # Veri özeti
    report_lines.append(f"\n📊 VERİ ÖZETİ")
    report_lines.append("-" * 40)
    report_lines.append(f"Toplam Satır (Tahmin Zamanı): {len(matrix)}")
    report_lines.append(f"Toplam Sütun (Hedef Hafta): {len(matrix.columns)}")
    report_lines.append(f"Tahmin Horizonları: {sorted(forecasts_by_horizon.keys())}")
    
    # Horizon bazlı analiz
    report_lines.append(f"\n📈 HORİZON BAZLI HATA ANALİZİ")
    report_lines.append("-" * 40)
    
    horizon_analysis = analyze_by_horizon(forecasts_by_horizon, actuals)
    
    # Tablo formatı
    report_lines.append(f"{'Horizon':>8} {'Bias':>12} {'Std':>12} {'RMSE':>12} {'MAE':>12} {'N':>6}")
    report_lines.append("-" * 64)
    
    for _, row in horizon_analysis.iterrows():
        report_lines.append(
            f"{int(row['Horizon']):>8} "
            f"{row['Bias']:>12.2f} "
            f"{row['Error_Std']:>12.2f} "
            f"{row['RMSE']:>12.2f} "
            f"{row['MAE']:>12.2f} "
            f"{int(row['Sample_Size']):>6}"
        )
    
    # Bias yorumu
    avg_bias = horizon_analysis['Bias'].mean()
    report_lines.append(f"\n💡 Ortalama Bias: {avg_bias:.2f}")
    if avg_bias > 0:
        report_lines.append("   → Tahminler genellikle gerçekten YÜKSEK (iyimser)")
    elif avg_bias < 0:
        report_lines.append("   → Tahminler genellikle gerçekten DÜŞÜK (kötümser)")
    else:
        report_lines.append("   → Tahminler sapmasız (unbiased)")
    
    # Revizyon oynaklığı analizi
    report_lines.append(f"\n🔄 REVİZYON OYNAKLIĞI ANALİZİ")
    report_lines.append("-" * 40)
    
    volatility = calculate_revision_volatility(revision_pairs)
    
    report_lines.append(f"{'Horizon':>8} {'Ort.Rev':>12} {'Std.Rev':>12} {'Ort.|Rev|':>12} {'N':>6}")
    report_lines.append("-" * 52)
    
    for horizon, metrics in sorted(volatility.items()):
        report_lines.append(
            f"{horizon:>8} "
            f"{metrics['mean_revision']:>12.2f} "
            f"{metrics['std_revision']:>12.2f} "
            f"{metrics['mean_abs_revision']:>12.2f} "
            f"{int(metrics['count']):>6}"
        )
    
    # Revizyon yorumu
    if volatility:
        avg_volatility = np.mean([m['std_revision'] for m in volatility.values()])
        report_lines.append(f"\n💡 Ortalama Revizyon Std: {avg_volatility:.2f}")
        
        # Revizyon yönü analizi
        total_revisions = sum(m['count'] for m in volatility.values())
        mean_rev_weighted = sum(m['mean_revision'] * m['count'] for m in volatility.values()) / total_revisions
        
        if mean_rev_weighted > 0:
            report_lines.append("   → Revizyonlar genellikle YUKARIya doğru")
        elif mean_rev_weighted < 0:
            report_lines.append("   → Revizyonlar genellikle AŞAĞIya doğru")
    
    report_lines.append("\n" + "=" * 60)
    
    return "\n".join(report_lines)


if __name__ == "__main__":
    # Test
    from data_loader import create_sample_data, extract_actuals, extract_forecasts_by_horizon
    
    sample_df = create_sample_data(10)
    
    print("Örnek veri ile test:")
    print(generate_full_report(sample_df))
