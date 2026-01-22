# Rolling Forecast & Stock Planning

Bu proje, **gerçek zamanlı Chronos tahminleri** kullanarak tahmine dayalı dinamik stok planlaması yapar.

##  Sistem Özellikleri

### Gerçek Zamanlı Rolling Forecast
-  Her hafta için **sadece o ana kadar olan geçmiş veri** kullanılır
-  **Look-ahead bias engellenir** (gelecek bilgisi sızması yok)
-  **Hibrit tahmin sistemi**: Chronos + EDI performans bazlı ağırlıklı ortalama
-  **Dinamik model güncelleme**: Her hafta yeni veriyle tahmin güncellenir

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

### Hibrit Tahmin Sistemi
1. **Chronos Tahmini**: Geçmiş veriden gerçek zamanlı tahmin
2. **EDI Tahmini**: Geçmiş EDI tahminlerinin ortalaması
3. **Performans Değerlendirmesi**: Son 3 hafta RMSE karşılaştırması
4. **Ağırlıklı Kombinasyon**: Düşük hatalı kaynak daha yüksek ağırlık alır

##  Önemli Notlar
-  **İlk Çalıştırma**: Chronos modeli ilk seferde indirilir (~100-500 MB)
-  **Tahmin Geçmişi**: Gerçek zamanlı yapılan tahminler `chronos_forecasts.json`'a kaydedilir
-  **Model Boyutu**: Production için `tiny` model önerilir (hız/doğruluk dengesi)
-  **Performans**: Her tahmin ~1-3 saniye sürer (model boyutuna göre)

##  Test ve Geliştirme
Farklı model boyutlarını karşılaştırmak için:

```bash
# Hızlı test (tiny model)
python main/main.py --data "main/data.csv" --current-week 10 --lead-time 4 --model-size tiny

# Yüksek doğruluk (large model - daha yavaş)
python main/main.py --data "main/data.csv" --current-week 10 --lead-time 4 --model-size large
```
