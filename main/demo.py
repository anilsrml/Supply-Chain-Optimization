"""
Örnek Veri Üretici ve Test Modülü
Demo amaçlı örnek EDI verileri oluşturur
"""

import pandas as pd
import numpy as np
from typing import Tuple
import os


def generate_sample_edi_data(
    num_weeks: int = 20,
    base_demand: float = 100,
    noise_std: float = 15,
    trend: float = 0.5,
    bias_factor: float = 1.1,
    output_path: str = None
) -> pd.DataFrame:
    """
    Örnek EDI tahmin matrisi oluşturur.
    
    Matris yapısı:
    - Satırlar (index): Tahmin yapılan hafta (forecast_week)
    - Sütunlar: Hedef hafta (target_week)
    - Üst üçgen: Tahminler
    - Diagonal: Gerçekleşen değerler
    
    Args:
        num_weeks: Toplam hafta sayısı
        base_demand: Temel talep seviyesi
        noise_std: Gürültü standart sapması
        trend: Haftalık trend (pozitif = artan)
        bias_factor: Tahmin bias faktörü (>1 = over-forecast)
        output_path: CSV kayıt yolu
        
    Returns:
        EDI tahmin matrisi DataFrame
    """
    np.random.seed(42)
    
    # Gerçek talep serisi oluştur (trend + noise)
    actual_demands = []
    for week in range(1, num_weeks + 1):
        demand = base_demand + trend * week + np.random.normal(0, noise_std)
        actual_demands.append(max(0, demand))
    
    # Tahmin matrisi oluştur
    weeks = list(range(1, num_weeks + 1))
    matrix = pd.DataFrame(index=weeks, columns=weeks, dtype=float)
    
    for forecast_week in weeks:
        for target_week in weeks:
            if target_week == forecast_week:
                # Diagonal: Gerçekleşen değer
                matrix.loc[forecast_week, target_week] = actual_demands[target_week - 1]
            elif target_week > forecast_week:
                # Üst üçgen: Tahmin
                horizon = target_week - forecast_week
                actual = actual_demands[target_week - 1]
                
                # Tahmin = Gerçek * bias + horizon-bağımlı gürültü
                # Uzak horizonlarda daha fazla hata
                horizon_noise = np.random.normal(0, noise_std * (1 + horizon * 0.1))
                forecast = actual * bias_factor + horizon_noise
                
                matrix.loc[forecast_week, target_week] = max(0, forecast)
            # Alt üçgen: NaN (henüz tahmin yapılmamış)
    
    if output_path:
        matrix.to_csv(output_path)
        print(f"Örnek veri kaydedildi: {output_path}")
    
    return matrix


def generate_multiple_scenarios(output_dir: str) -> dict:
    """Farklı senaryolar için örnek veriler oluşturur"""
    
    os.makedirs(output_dir, exist_ok=True)
    
    scenarios = {
        'stable_demand': {
            'base_demand': 100,
            'noise_std': 10,
            'trend': 0,
            'bias_factor': 1.0,
            'description': 'Sabit talep, düşük değişkenlik'
        },
        'growing_demand': {
            'base_demand': 80,
            'noise_std': 15,
            'trend': 2.0,
            'bias_factor': 1.05,
            'description': 'Artan trend, orta değişkenlik'
        },
        'volatile_demand': {
            'base_demand': 100,
            'noise_std': 30,
            'trend': 0.5,
            'bias_factor': 1.15,
            'description': 'Yüksek değişkenlik, over-forecast bias'
        },
        'declining_demand': {
            'base_demand': 150,
            'noise_std': 12,
            'trend': -1.5,
            'bias_factor': 0.95,
            'description': 'Azalan trend, under-forecast bias'
        }
    }
    
    for name, params in scenarios.items():
        filepath = os.path.join(output_dir, f'{name}.csv')
        generate_sample_edi_data(
            num_weeks=20,
            base_demand=params['base_demand'],
            noise_std=params['noise_std'],
            trend=params['trend'],
            bias_factor=params['bias_factor'],
            output_path=filepath
        )
        print(f"  {name}: {params['description']}")
    
    return scenarios


def run_demo():
    """Demo çalıştırır"""
    print("="*60)
    print("TAHMİNE DAYALI DİNAMİK STOK PLANLAMA SİSTEMİ - DEMO")
    print("="*60)
    
    # Örnek veri oluştur
    print("\n1. Örnek EDI verileri oluşturuluyor...")
    sample_data_path = os.path.join(os.path.dirname(__file__), 'sample_data')
    scenarios = generate_multiple_scenarios(sample_data_path)
    
    # Sistem başlat
    print("\n2. Sistem başlatılıyor...")
    from orchestrator import StockPlanningOrchestrator
    
    orchestrator = StockPlanningOrchestrator(chronos_model_size="tiny")
    
    # Malzeme yükle (stable_demand senaryosu)
    print("\n3. Malzeme verisi yükleniyor...")
    material = orchestrator.load_material_data(
        filepath=os.path.join(sample_data_path, 'stable_demand.csv'),
        material_id='MAT001',
        lead_time_weeks=4,
        current_stock=200,
        service_level=0.95
    )
    
    print(f"Yüklenen malzeme: {material.material_id}")
    print(f"Lead time: {material.lead_time_weeks} hafta")
    print(f"Mevcut stok: {material.current_stock}")
    print(f"Servis seviyesi: {material.service_level*100:.0f}%")
    print(f"EDI tahmin sayısı: {len(material.edi_forecasts)}")
    print(f"Gerçekleşen tüketim sayısı: {len(material.actual_consumptions)}")
    
    # Horizon hatalarını göster
    print("\n4. Horizon bazlı hata metrikleri:")
    for horizon in range(1, 9):
        error = orchestrator.get_horizon_error('MAT001', horizon)
        if error:
            print(f"  Horizon {horizon}: Bias={error.bias:+.2f}, RMSE={error.rmse:.2f}, N={error.sample_count}")
    
    # Tek hafta planlaması
    print("\n5. Tek hafta planlama örneği...")
    decision = orchestrator.run_weekly_planning('MAT001', current_week=10)
    
    # Simülasyon
    print("\n6. Simülasyon çalıştırılıyor...")
    decisions = orchestrator.run_simulation(
        material_id='MAT001',
        start_week=10,
        end_week=15,
        initial_stock=200
    )
    
    # Özet rapor
    print("\n7. Özet Rapor:")
    report = orchestrator.get_summary_report('MAT001', decisions)
    print(f"  Dönem: Hafta {report['period']['start_week']} - {report['period']['end_week']}")
    print(f"  Toplam sipariş: {report['orders']['count']} adet, {report['orders']['total_quantity']:.2f} birim")
    print(f"  Ortalama emniyet stoğu: {report['inventory']['avg_safety_stock']:.2f}")
    print(f"  Ortalama reorder point: {report['inventory']['avg_reorder_point']:.2f}")
    
    print("\n" + "="*60)
    print("DEMO TAMAMLANDI")
    print("="*60)


if __name__ == "__main__":
    run_demo()
