"""
Chronos Veri Üretici Test Dosyası
Tüm olası current_week ve lead_time senaryoları için Chronos tahminlerini üretir ve JSON'a kaydeder.
"""

import sys
import os
import json
from typing import Dict, List

# Modülleri import et
from edi_processor import EDIProcessor
from chronos_forecaster import ChronosForecaster


def generate_all_chronos_forecasts(
    data_filepath: str = "data.csv",
    material_id: str = "MAT001",
    output_filepath: str = "chronos_forecasts.json",
    max_week: int = 13,
    max_lead_time: int = 5,
    force_regenerate: bool = False
):
    """
    Tüm olası current_week ve lead_time kombinasyonları için Chronos tahminleri üretir.
    
    Args:
        data_filepath: CSV veri dosyası yolu
        material_id: Malzeme ID
        output_filepath: Çıktı JSON dosyası
        max_week: Maksimum hafta sayısı (veri setindeki son hafta)
        max_lead_time: Maksimum lead time (kaç hafta ileri tahmin yapılacak)
        force_regenerate: True ise mevcut tahminleri görmezden gelir ve yeniden üretir
    """
    print("=" * 70)
    print("CHRONOS VERİ ÜRETİCİ TEST SİSTEMİ")
    print("=" * 70)
    print(f"Veri Dosyası: {data_filepath}")
    print(f"Malzeme ID: {material_id}")
    print(f"Maksimum Hafta: {max_week}")
    print(f"Maksimum Lead Time: {max_lead_time}")
    print("=" * 70)
    
    # Mevcut JSON dosyasını kontrol et
    existing_forecasts = {}
    if os.path.exists(output_filepath) and not force_regenerate:
        try:
            with open(output_filepath, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
                if material_id in existing_data:
                    existing_forecasts = {
                        (f['forecast_week'], f['target_week']): f 
                        for f in existing_data[material_id]
                    }
                    print(f"\n✓ Mevcut JSON dosyası bulundu: {len(existing_forecasts)} tahmin mevcut.")
                    print(f"  Sadece eksik tahminler üretilecek.")
        except Exception as e:
            print(f"\n⚠ Mevcut dosya okunamadı: {str(e)}")
            print(f"  Tüm tahminler yeniden üretilecek.")
    elif force_regenerate:
        print(f"\n⚠ Force regenerate aktif: Tüm tahminler yeniden üretilecek.")
    
    # EDI Processor'ı başlat ve veriyi yükle
    print("\n[1/4] EDI verisi yükleniyor...")
    processor = EDIProcessor()
    material = processor.load_from_csv(
        filepath=data_filepath,
        material_id=material_id,
        lead_time_weeks=1,  # Başlangıç değeri, her senaryo için değişecek
        current_stock=0,
        service_level=0.95
    )
    print(f"✓ Veri yüklendi: {len(material.actual_consumptions)} gerçekleşen değer bulundu.")
    
    # Chronos modelini başlat (sadece yeni tahmin gerekiyorsa)
    forecaster = None
    needs_forecast = False
    
    # Önce eksik tahminleri tespit et
    for current_week in range(1, max_week + 1):
        for lead_time in range(1, max_lead_time + 1):
            target_week = current_week + lead_time
            if target_week > max_week:
                continue
            if (current_week, target_week) not in existing_forecasts:
                needs_forecast = True
                break
        if needs_forecast:
            break
    
    if not needs_forecast and existing_forecasts:
        print("\n✓ Tüm tahminler zaten mevcut, yeni tahmin üretilmeyecek.")
        print("  (Yeniden üretmek için force_regenerate=True kullanın)")
        return existing_data
    
    print("\n[2/4] Chronos modeli yükleniyor...")
    forecaster = ChronosForecaster(model_size="tiny")  # Hız için tiny model
    print("✓ Chronos modeli hazır.")
    
    # Tüm senaryolar için tahmin üret
    print("\n[3/4] Tahminler kontrol ediliyor ve eksikler üretiliyor...")
    all_forecasts = list(existing_forecasts.values())  # Mevcut tahminlerle başla
    total_scenarios = 0
    successful_scenarios = 0
    skipped_scenarios = 0
    
    for current_week in range(1, max_week + 1):
        # Bu haftaya kadar olan geçmiş veriyi al
        historical = processor.get_historical_series(material_id, current_week)
        
        # En az 2 veri noktası gerekli
        if len(historical) < 2:
            print(f"  ⚠ Hafta {current_week}: Yetersiz geçmiş veri (en az 2 gerekli)")
            continue
        
        for lead_time in range(1, max_lead_time + 1):
            target_week = current_week + lead_time
            
            # Hedef hafta veri setinin dışında kalıyorsa atla
            if target_week > max_week:
                continue
            
            total_scenarios += 1
            
            # Zaten varsa atla
            if (current_week, target_week) in existing_forecasts:
                skipped_scenarios += 1
                print(f"  ⊙ Hafta {current_week} → Hafta {target_week} (LT={lead_time}): Zaten mevcut, atlandı")
                continue
            
            try:
                # Chronos tahmini yap
                forecast_value = forecaster.forecast_single_week(historical, lead_time)
                
                # Kaydı oluştur
                forecast_entry = {
                    'forecast_week': current_week,
                    'target_week': target_week,
                    'forecast_value': float(forecast_value),
                    'lead_time': lead_time,
                    'historical_data_points': len(historical)
                }
                
                all_forecasts.append(forecast_entry)
                successful_scenarios += 1
                
                print(f"  ✓ Hafta {current_week} → Hafta {target_week} (LT={lead_time}): {forecast_value:.2f} (YENİ)")
                
            except Exception as e:
                print(f"  ✗ Hafta {current_week} → Hafta {target_week} (LT={lead_time}): HATA - {str(e)}")
    
    print(f"\n✓ Tahmin üretimi tamamlandı:")
    print(f"  - Toplam Senaryo: {total_scenarios}")
    print(f"  - Mevcut (Atlandı): {skipped_scenarios}")
    print(f"  - Yeni Üretilen: {successful_scenarios}")
    print(f"  - Toplam Kayıt: {len(all_forecasts)}")
    
    # JSON dosyasına kaydet
    print(f"\n[4/4] Tahminler JSON dosyasına kaydediliyor: {output_filepath}")
    
    # Yeni veriyi ekle
    output_data = {
        material_id: all_forecasts
    }
    
    # Dosyaya yaz
    with open(output_filepath, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"✓ {len(all_forecasts)} tahmin kaydedildi.")
    
    # Özet rapor
    print("\n" + "=" * 70)
    print("ÖZET RAPOR")
    print("=" * 70)
    print(f"Toplam Senaryo: {total_scenarios}")
    print(f"Zaten Mevcut: {skipped_scenarios}")
    print(f"Yeni Başarılı: {successful_scenarios}")
    print(f"Başarısız: {total_scenarios - successful_scenarios - skipped_scenarios}")
    print(f"Toplam Kayıt: {len(all_forecasts)}")
    print(f"Çıktı Dosyası: {output_filepath}")
    print("=" * 70)
    
    return output_data


def verify_json_file(filepath: str = "chronos_forecasts.json"):
    """
    Oluşturulan JSON dosyasını doğrular ve özet bilgi verir.
    
    Args:
        filepath: JSON dosya yolu
    """
    print("\n" + "=" * 70)
    print("JSON DOSYASI DOĞRULAMA")
    print("=" * 70)
    
    if not os.path.exists(filepath):
        print(f"✗ Dosya bulunamadı: {filepath}")
        return False
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"✓ Dosya başarıyla okundu: {filepath}")
        print(f"\nİçerik:")
        
        for material_id, forecasts in data.items():
            print(f"  Malzeme ID: {material_id}")
            print(f"  Toplam Tahmin: {len(forecasts)}")
            
            if forecasts:
                # İlk ve son kayıt
                first = forecasts[0]
                last = forecasts[-1]
                print(f"  İlk Kayıt: Hafta {first['forecast_week']} → {first['target_week']} = {first['forecast_value']:.2f}")
                print(f"  Son Kayıt: Hafta {last['forecast_week']} → {last['target_week']} = {last['forecast_value']:.2f}")
                
                # Hafta aralığı
                weeks = sorted(set(f['forecast_week'] for f in forecasts))
                print(f"  Hafta Aralığı: {min(weeks)} - {max(weeks)}")
        
        print("\n✓ Doğrulama başarılı!")
        return True
        
    except Exception as e:
        print(f"✗ Dosya doğrulama hatası: {str(e)}")
        return False


if __name__ == "__main__":
    """
    Test dosyasını çalıştır.
    
    Kullanım:
        python test_chronos_data_generator.py              # Eksik tahminleri üret
        python test_chronos_data_generator.py --force      # Tümünü yeniden üret
    """
    import argparse
    
    # Komut satırı argümanlarını parse et
    parser = argparse.ArgumentParser(description="Chronos tahmin verilerini üret")
    parser.add_argument(
        '--force',
        action='store_true',
        help='Mevcut tahminleri görmezden gel ve tümünü yeniden üret'
    )
    args = parser.parse_args()
    
    # Çalışma dizinini main klasörüne ayarla
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    print("\n🚀 Test başlatılıyor...\n")
    
    try:
        # Tüm tahminleri üret
        result = generate_all_chronos_forecasts(
            data_filepath="data.csv",
            material_id="MAT001",
            output_filepath="chronos_forecasts.json",
            max_week=13,
            max_lead_time=5,
            force_regenerate=args.force
        )
        
        # Dosyayı doğrula
        verify_json_file("chronos_forecasts.json")
        
        print("\n✅ Test başarıyla tamamlandı!")
        
    except Exception as e:
        print(f"\n❌ Test sırasında hata oluştu: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
