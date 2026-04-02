"""
Tahmine Dayalı Dinamik Stok Planlama Sistemi
Ana giriş noktası
"""

import os
import sys
from pathlib import Path


def _default_data_path() -> str:
    """Proje kökü (stok_projesi) altındaki data_safety_stock.xlsx."""
    return str(Path(__file__).resolve().parents[2] / "data_safety_stock.xlsx")


# GERÇEK ZAMANLI CHRONOS TAHMİNİ
# Sistem artık her hafta için Chronos tahminlerini gerçek zamanlı olarak üretir.
# Önceden üretilmiş tahminler yerine, rolling forecast mantığına uygun
# dinamik tahminler yapılır. Bu sayede:
# - Gelecek bilgisi sızması (look-ahead bias) engellenir
# - Rolling forecast prensiplerine uygun çalışır
# - Her hafta sadece o ana kadar olan geçmiş veri kullanılır


def main():
    """
    Sistem kullanım örneği.
    
    Bu script, stok planlama sisteminin temel kullanımını gösterir.
    Kendi verilerinizle kullanmak için:
    
    1. EDI tahmin matrisinizi CSV olarak hazırlayın
       - Satırlar: Tahmin yapılan hafta
       - Sütunlar: Hedef hafta
       - Üst üçgen: Tahminler
       - Köşegenin hemen altı (fw=tw+1): Gerçekleşen değerler
    
    2. Orchestrator'ı başlatın:
       orchestrator = StockPlanningOrchestrator()
    
    3. Malzeme verilerinizi yükleyin:
       orchestrator.load_material_data(
           filepath='veri.csv',
           material_id='MAL001',
           lead_time_weeks=4,
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
        default=None,
        help=(
            'EDI veri dosyası (.xlsx data_safety_stock veya CSV). '
            'Verilmezse: proje kökünde data_safety_stock.xlsx kullanılır.'
        ),
    )

    parser.add_argument(
        '--material-id',
        type=str,
        required=True,
        help='Materyal kodu (Excel: Material - Key; örn. M100F133RO)',
    )
    
    parser.add_argument(
        '--lead-time',
        type=int,
        default=4,
        help='Lead time hafta sayısı (varsayılan: 4)'
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
        default='bolt-base',
        choices=['bolt-tiny', 'bolt-mini', 'bolt-small', 'bolt-base', 'tiny', 'mini', 'small', 'base', 'large'],
        help='Chronos model boyutu (varsayılan: bolt-base)'
    )

    parser.add_argument(
        '--use-column-forecast',
        action='store_true',
        default=False,
        help='Chronos tahmininde EDI sutun yakinsama serisini kullan (varsayilan: kapali)'
    )

    args = parser.parse_args()

    data_path = args.data if args.data else _default_data_path()
    if not os.path.isfile(data_path):
        print(f"HATA: Veri dosyası bulunamadı: {data_path}")
        sys.exit(1)

    if str(data_path).lower().endswith((".xlsx", ".xls")):
        from excel_data_loader import ExcelDataLoader

        try:
            ExcelDataLoader.validate_material_code(data_path, args.material_id)
        except ValueError as e:
            print(str(e))
            sys.exit(2)

    from orchestrator import StockPlanningOrchestrator

    # Gerçek zamanlı Chronos tahmini - sistem her hafta için dinamik olarak tahmin yapar
    print("\n" + "="*60)
    print("GERCEK ZAMANLI CHRONOS TAHMIN SISTEMI")
    print("="*60)
    print("[+] Rolling forecast mantığına uygun dinamik tahminler")
    print("[+] Her hafta sadece geçmiş veri kullanılır")
    print("[+] Look-ahead bias engellenir")
    print("="*60)

    print("\nSistem başlatılıyor...")
    orchestrator = StockPlanningOrchestrator(
        chronos_model_size=args.model_size,
        use_column_forecast=args.use_column_forecast
    )

    print(f"Veri yükleniyor: {data_path}")
    try:
        orchestrator.load_material_data(
            filepath=data_path,
            material_id=args.material_id,
            lead_time_weeks=args.lead_time,
        )
    except ValueError as e:
        print(str(e))
        sys.exit(2)
    
    print(f"\nHafta {args.current_week} için planlama yapılıyor...")
    decision = orchestrator.run_weekly_planning(
        args.material_id,
        current_week=args.current_week
    )


if __name__ == "__main__":
    main()
