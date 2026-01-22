# Rolling Forecast & Stock Planning

Bu proje, **gerçek zamanlı Chronos tahminleri** kullanarak tahmine dayalı dinamik stok planlaması yapar.

## 🎯 Sistem Özellikleri

### Gerçek Zamanlı Rolling Forecast
- ✅ Her hafta için **sadece o ana kadar olan geçmiş veri** kullanılır
- ✅ **Look-ahead bias engellenir** (gelecek bilgisi sızması yok)
- ✅ **Hibrit tahmin sistemi**: Chronos + EDI performans bazlı ağırlıklı ortalama
- ✅ **Dinamik model güncelleme**: Her hafta yeni veriyle tahmin güncellenir

### Teknik Detaylar
- **Chronos Model**: Amazon Chronos-T5 foundation model
- **EDI Entegrasyonu**: Geçmiş EDI tahminleri ile karşılaştırma
- **Performans Metriği**: Son 3 hafta RMSE bazlı kaynak seçimi
- **Bias Düzeltme**: Horizon bazlı sistematik hata düzeltmesi

##  Hızlı Başlangıç

### 1. Gereksinimleri Yükleyin
Terminalinizi açın ve aşağıdaki komutu çalıştırarak gerekli kütüphaneleri yükleyin:

```bash
pip install -r main/requirements.txt
```

### 2. Sistemi Çalıştırın
Tek hafta için planlama:

```bash
python main/main.py --data "main/data.csv" --current-week 4 --lead-time 1 --current-stock 0 --model-size tiny
```

## 📋 Parametre Açıklamaları
- `--data`: Kullanılacak veri dosyasının yolu (CSV)
- `--current-week`: Planlamanın yapılacağı mevcut hafta
- `--lead-time`: Tedarik süresi (hafta bazında)
- `--current-stock`: Mevcut stok miktarı
- `--model-size`: Chronos model boyutu (önerilen: `tiny` - hızlı, `small` - dengeli, `large` - en doğru)

## 🔍 Nasıl Çalışır?

### Rolling Forecast Prensibi
```
Hafta 4'te tahmin yapılırken:
  ✓ Kullanılan: Hafta 1, 2, 3 gerçekleşen değerler
  ✗ Kullanılmayan: Hafta 4'ten sonraki veriler

Hafta 5'te tahmin yapılırken:
  ✓ Kullanılan: Hafta 1, 2, 3, 4 gerçekleşen değerler
  ✗ Kullanılmayan: Hafta 5'ten sonraki veriler
```

### Geriye Dönük Tahmin (Backfilling)
Sistem ilk çalıştığında, geçmiş haftalar için de tahminler üretir:

```
Hafta 4'te sistem başladığında:
  1. Hafta 1 verisi ile → Hafta 2 tahmini (geçmişe dönük)
  2. Hafta 1-2 verisi ile → Hafta 3 tahmini (geçmişe dönük)
  3. Hafta 1-2-3 verisi ile → Hafta 4 tahmini (geçmişe dönük)
  4. Hafta 1-2-3-4 verisi ile → Hafta 5 tahmini (mevcut)

Avantaj: Performans karşılaştırması için yeterli veri sağlanır
```

### Hibrit Tahmin Sistemi
1. **Chronos Tahmini**: Geçmiş veriden gerçek zamanlı tahmin
2. **EDI Tahmini**: Geçmiş EDI tahminlerinin ortalaması
3. **Performans Değerlendirmesi**: Son 3 hafta RMSE karşılaştırması
4. **Ağırlıklı Kombinasyon**: Düşük hatalı kaynak daha yüksek ağırlık alır

## 📋 Önemli Notlar
- ⚡ **İlk Çalıştırma**: Chronos modeli ilk seferde indirilir (~100-500 MB)
- 💾 **Tahmin Geçmişi**: Gerçek zamanlı yapılan tahminler `chronos_forecasts.json`'a kaydedilir
- 🎯 **Model Boyutu**: Production için `tiny` model önerilir (hız/doğruluk dengesi)
- 📊 **Performans**: Her tahmin ~1-3 saniye sürer (model boyutuna göre)

## 🧪 Test ve Geliştirme
Farklı model boyutlarını karşılaştırmak için:

```bash
# Hızlı test (tiny model)
python main/main.py --data "main/data.csv" --current-week 10 --lead-time 4 --model-size tiny

# Yüksek doğruluk (large model - daha yavaş)
python main/main.py --data "main/data.csv" --current-week 10 --lead-time 4 --model-size large
```
