"""
Veri yükleme ve matris işleme modülü.
Alt üçgen (gerçek) ve üst üçgen (tahmin) verilerini ayırır.
"""

import pandas as pd
import numpy as np


def load_triangle_data(file_path: str) -> pd.DataFrame:
    """
    CSV dosyasından üçgen matris verisini yükler.
    
    Beklenen format:
    - Satırlar: week1, week2, ... (tahmin yapılan zaman)
    - Sütunlar: w1, w2, ... (hedef hafta)
    
    Args:
        file_path: CSV dosyasının yolu
        
    Returns:
        DataFrame: Yüklenen matris verisi
    """
    df = pd.read_csv(file_path, index_col=0)
    return df


def get_diagonal_index(matrix: pd.DataFrame) -> dict:
    """
    Her sütun için köşegen indeksini hesaplar.
    Köşegen, gerçek değerin bulunduğu satırdır.
    
    Args:
        matrix: Üçgen matris
        
    Returns:
        dict: Sütun adı -> köşegen satır indeksi
    """
    n_rows = len(matrix)
    n_cols = len(matrix.columns)
    
    diagonal_map = {}
    for col_idx, col_name in enumerate(matrix.columns):
        # Köşegen satır indeksi: sütun indeksi kadar aşağıda
        diag_row_idx = min(col_idx, n_rows - 1)
        diagonal_map[col_name] = diag_row_idx
    
    return diagonal_map


def extract_actuals(matrix: pd.DataFrame) -> pd.Series:
    """
    Alt üçgenden (köşegen üzerinden) gerçekleşen değerleri çıkarır.
    Her sütun için köşegen değeri gerçek değerdir.
    
    Args:
        matrix: Üçgen matris
        
    Returns:
        Series: Her hedef hafta için gerçekleşen değer
    """
    actuals = {}
    n_rows = len(matrix)
    
    for col_idx, col_name in enumerate(matrix.columns):
        # Köşegen satırı: sütun indeksi kadar aşağıda (0'dan başlayarak)
        diag_row_idx = min(col_idx, n_rows - 1)
        actuals[col_name] = matrix.iloc[diag_row_idx, col_idx]
    
    return pd.Series(actuals)


def extract_forecasts_by_horizon(matrix: pd.DataFrame) -> dict:
    """
    Üst üçgenden tahminleri horizon bazlı çıkarır.
    
    Horizon = köşegenden kaç satır yukarıda olduğu
    - Horizon 1: Bir önceki tahmin
    - Horizon 2: İki önceki tahmin
    - vs.
    
    Args:
        matrix: Üçgen matris
        
    Returns:
        dict: {horizon: {hedef_hafta: tahmin_değeri}}
    """
    forecasts_by_horizon = {}
    n_rows = len(matrix)
    n_cols = len(matrix.columns)
    
    for col_idx, col_name in enumerate(matrix.columns):
        diag_row_idx = min(col_idx, n_rows - 1)
        
        # Köşegenin üstündeki tüm satırlar tahmindir
        for row_idx in range(diag_row_idx):
            horizon = diag_row_idx - row_idx  # Kaç satır yukarıda
            
            if horizon not in forecasts_by_horizon:
                forecasts_by_horizon[horizon] = {}
            
            forecasts_by_horizon[horizon][col_name] = matrix.iloc[row_idx, col_idx]
    
    return forecasts_by_horizon


def get_revision_pairs(matrix: pd.DataFrame) -> dict:
    """
    Ardışık tahminler arasındaki revizyonları çıkarır.
    
    Args:
        matrix: Üçgen matris
        
    Returns:
        dict: {hedef_hafta: [(eski_tahmin, yeni_tahmin, horizon), ...]}
    """
    revision_pairs = {}
    n_rows = len(matrix)
    
    for col_idx, col_name in enumerate(matrix.columns):
        diag_row_idx = min(col_idx, n_rows - 1)
        revision_pairs[col_name] = []
        
        # Üst üçgendeki ardışık tahminleri al
        for row_idx in range(diag_row_idx - 1):
            old_forecast = matrix.iloc[row_idx, col_idx]
            new_forecast = matrix.iloc[row_idx + 1, col_idx]
            horizon = diag_row_idx - row_idx - 1  # Yeni tahminin horizonu
            
            revision_pairs[col_name].append({
                'old_forecast': old_forecast,
                'new_forecast': new_forecast,
                'revision': new_forecast - old_forecast,
                'horizon': horizon
            })
    
    return revision_pairs


def create_sample_data(n_weeks: int = 12) -> pd.DataFrame:
    """
    Test amaçlı örnek üçgen matris verisi oluşturur.
    
    Args:
        n_weeks: Hafta sayısı
        
    Returns:
        DataFrame: Örnek üçgen matris
    """
    np.random.seed(42)
    
    # Boş matris oluştur
    data = np.zeros((n_weeks, n_weeks))
    
    # Gerçek değerler (köşegen)
    base_values = np.random.uniform(-2000, -500, n_weeks)
    
    for col_idx in range(n_weeks):
        # Köşegen değeri (gerçek)
        diag_row_idx = min(col_idx, n_weeks - 1)
        actual = base_values[col_idx]
        data[diag_row_idx, col_idx] = actual
        
        # Üst üçgen (tahminler) - horizona göre artan hata ile
        for row_idx in range(diag_row_idx):
            horizon = diag_row_idx - row_idx
            noise = np.random.normal(0, 50 * horizon)  # Horizon arttıkça hata artar
            bias = 20 * horizon  # Küçük bir pozitif sapma
            data[row_idx, col_idx] = actual + noise + bias
    
    # DataFrame oluştur
    row_labels = [f'week{i+1}' for i in range(n_weeks)]
    col_labels = [f'w{i+1}' for i in range(n_weeks)]
    
    df = pd.DataFrame(data, index=row_labels, columns=col_labels)
    return df


if __name__ == "__main__":
    # Test
    sample_df = create_sample_data(10)
    print("Örnek Matris:")
    print(sample_df.round(0).to_string())
    print("\n" + "="*50)
    
    actuals = extract_actuals(sample_df)
    print("\nGerçekleşen Değerler:")
    print(actuals.round(0))
    
    forecasts = extract_forecasts_by_horizon(sample_df)
    print(f"\nTahmin Horizonları: {list(forecasts.keys())}")
