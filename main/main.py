"""
Tahmine Dayalı Dinamik Stok Planlama Sistemi
Ana giriş noktası
"""

from orchestrator import StockPlanningOrchestrator


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
    
    args = parser.parse_args()
    
    # Veri ile çalıştır
    print("Sistem başlatılıyor...")
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
