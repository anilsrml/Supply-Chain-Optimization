"""
Tahmin Revizyon Analizi - Ana Çalıştırma Scripti

Kullanım:
    python main.py --file "veri_dosya_yolu.csv"
    python main.py --test  # Örnek veri ile test
"""

import argparse
import sys

from data_loader import load_triangle_data, create_sample_data
from revision_analysis import generate_full_report


def main():
    parser = argparse.ArgumentParser(
        description='Tahmin Revizyon Analizi',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
    python main.py --file "data.csv"
    python main.py --test
        """
    )
    
    parser.add_argument(
        '--file', '-f',
        type=str,
        help='CSV veri dosyasının yolu'
    )
    
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='Örnek veri ile test modunda çalıştır'
    )
    
    args = parser.parse_args()
    
    # Argüman kontrolü
    if not args.file and not args.test:
        parser.print_help()
        print("\n❌ Hata: --file veya --test parametresi gerekli!")
        sys.exit(1)
    
    # Veri yükle
    if args.test:
        print("🔬 Test modu: Örnek veri oluşturuluyor...")
        matrix = create_sample_data(12)
        print("\nÖrnek Matris (ilk 6 satır/sütun):")
        print(matrix.iloc[:6, :6].round(0).to_string())
        print("\n")
    else:
        print(f"📂 Veri yükleniyor: {args.file}")
        try:
            matrix = load_triangle_data(args.file)
            print(f"✅ Veri yüklendi: {matrix.shape[0]} satır x {matrix.shape[1]} sütun")
        except FileNotFoundError:
            print(f"❌ Hata: Dosya bulunamadı: {args.file}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Hata: {e}")
            sys.exit(1)
    
    # Rapor oluştur
    print("\n" + generate_full_report(matrix))


if __name__ == "__main__":
    main()
