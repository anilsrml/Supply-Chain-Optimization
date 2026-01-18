# Rolling Forecast & Stock Planning

Bu proje, Chronos kullanarak tahmine dayalı dinamik stok planlaması yapar.

##  Hızlı Başlangıç

### 1. Gereksinimleri Yükleyin
Terminalinizi açın ve aşağıdaki komutu çalıştırarak gerekli kütüphaneleri yükleyin:

```bash
pip install -r main/requirements.txt
```

### 2. Sistemi Çalıştırın
Sistemi belirli parametrelerle çalıştırmak için terminalde şu komutu kullanın:

```bash
python main/main.py --data "main/data.csv" --current-week 4 --lead-time 1 --current-stock 0 --model-size large
```

<<<<<<< HEAD
## 📋 Parametre Açıklamaları
- `--data`: Kullanılacak veri dosyasının yolu (CSV).
- `--current-week`: Planlamanın yapılacağı mevcut hafta.
- `--lead-time`: Tedarik süresi (hafta bazında).
- `--current-stock`: Mevcut stok miktarı.
- `--model-size`: Kullanılacak Chronos modelinin boyutu (`tiny`, `mini`, `small`, `base`, `large`).

## 📋 Notlar
- Sonuçlar `main/forecast_results.xlsx` olarak kaydedilir.
=======
##  Notlar
- Veriler `main/data.csv` dosyasından okunur.
- Sonuçlar `main/forecast_results.xlsx` olarak kaydedilir.
- Chronos modeli ilk çalışmada gerekli ağırlıkları otomatik olarak indirecektir.
>>>>>>> fd4c599c3c673cf78f7d4a8440d7ebcbd54353d3
