"""
Tahmine Dayalı Dinamik Stok Planlama Sistemi
Ana giriş noktası
"""

import os
from orchestrator import StockPlanningOrchestrator


def ensure_chronos_forecasts_exist(data_filepath: str, material_id: str, max_week: int = 13):
    """
    Chronos tahminlerinin JSON dosyasında olduğundan emin olur.
    Yoksa otomatik olarak üretir.
    
    Args:
        data_filepath: CSV veri dosyası
        material_id: Malzeme ID
        max_week: Maksimum hafta sayısı
    """
    forecast_file = "chronos_forecasts.json"
    
    # JSON dosyası varsa ve içinde veri varsa, tekrar üretme
    if os.path.exists(forecast_file):
        import json
        try:
            with open(forecast_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if material_id in data and len(data[material_id]) > 0:
                    print(f"✓ Chronos tahminleri zaten mevcut ({len(data[material_id])} kayıt)")
                    return
        except:
            pass
    
    # JSON yoksa veya boşsa, test dosyasını çalıştır
    print("⚠ Chronos tahminleri bulunamadı, üretiliyor...")
    try:
        from test_chronos_data_generator import generate_all_chronos_forecasts
        generate_all_chronos_forecasts(
            data_filepath=data_filepath,
            material_id=material_id,
            output_filepath=forecast_file,
            max_week=max_week,
            max_lead_time=5,
            force_regenerate=False
        )
        print("✓ Chronos tahminleri başarıyla üretildi")
    except Exception as e:
        print(f"⚠ Chronos tahminleri üretilemedi: {str(e)}")
        print("  Sistem EDI tahminleri ile devam edecek")


def main():
    """
    Sistem kullanım örneği.
    
    Bu script, stok planlama sisteminin temel kullanımını gösterir.
    Kendi verilerinizle kullanmak için:
    
    1. EDI tahmin matrisinizi CSV olarak hazırlayın
       - Satırlar: Tahmin yapılan hafta
       - Sütunlar: Hedef hafta
       - Üst üçgen: Tahminler
       - Diagonal: Gerçekleşen değerler
    
    2. Orchestrator'ı başlatın:
       orchestrator = StockPlanningOrchestrator()
    
    3. Malzeme verilerinizi yükleyin:
       orchestrator.load_material_data(
           filepath='veri.csv',
           material_id='MAL001',
           lead_time_weeks=4,
           current_stock=100,
           service_level=0.95
       )
    
    4. Haftalık planlama yapın:
       decision = orchestrator.run_weekly_planning('MAL001', current_week=10)
    """
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Tahmine Dayalı Dinamik Stok Planlama Sistemi'
    )
    
    parser.add_argument(
        '--data',
        type=str,
        required=True,
        help='EDI veri dosyası yolu (CSV)'
    )
    
    parser.add_argument(
        '--material-id',
        type=str,
        default='MAT001',
        help='Malzeme ID (varsayılan: MAT001)'
    )
    
    parser.add_argument(
        '--lead-time',
        type=int,
        default=4,
        help='Lead time hafta sayısı (varsayılan: 4)'
    )
    
    parser.add_argument(
        '--current-stock',
        type=float,
        default=100,
        help='Mevcut stok seviyesi (varsayılan: 100)'
    )
    
    parser.add_argument(
        '--service-level',
        type=float,
        default=0.95,
        help='Hedef servis seviyesi (varsayılan: 0.95)'
    )
    
    parser.add_argument(
        '--current-week',
        type=int,
        default=10,
        help='Mevcut hafta numarası (varsayılan: 10)'
    )
    
    parser.add_argument(
        '--model-size',
        type=str,
        default='tiny',
        choices=['tiny', 'mini', 'small', 'base', 'large'],
        help='Chronos model boyutu (varsayılan: tiny)'
    )
    
    parser.add_argument(
        '--skip-chronos-check',
        action='store_true',
        help='Chronos tahmin kontrolünü atla (hızlı test için)'
    )
    
    args = parser.parse_args()
    
    # Chronos tahminlerini kontrol et ve gerekirse üret
    if not args.skip_chronos_check:
        ensure_chronos_forecasts_exist(
            data_filepath=args.data,
            material_id=args.material_id,
            max_week=13
        )
    
    # Veri ile çalıştır
    print("\nSistem başlatılıyor...")
    orchestrator = StockPlanningOrchestrator(chronos_model_size=args.model_size)
    
    print(f"Veri yükleniyor: {args.data}")
    orchestrator.load_material_data(
        filepath=args.data,
        material_id=args.material_id,
        lead_time_weeks=args.lead_time,
        current_stock=args.current_stock,
        service_level=args.service_level
    )
    
    print(f"\nHafta {args.current_week} için planlama yapılıyor...")
    decision = orchestrator.run_weekly_planning(
        args.material_id,
        current_week=args.current_week
    )


if __name__ == "__main__":
    main()
