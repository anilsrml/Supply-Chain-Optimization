# Rolling Forecast & Stock Planning

Gerçek zamanlı **Chronos** tahminleri ve **EDI** verileri kullanarak hibrit, tahmine dayalı dinamik stok planlaması yapan sistem. Hem komut satırı hem de **Streamlit web arayüzü** üzerinden kullanılabilir.

---

## Sistem Özellikleri

### Gerçek Zamanlı Rolling Forecast
- Her hafta için **yalnızca o ana kadar olan geçmiş veri** kullanılır
- **Look-ahead bias engellenir** — gelecek bilgisi sızması yok
- **Hibrit tahmin motoru**: Chronos + EDI performans bazlı ağırlıklı ortalama
- **Dinamik model güncelleme**: Her hafta yeni veriyle tahmin güncellenir

### Teknik Detaylar
- **Chronos Model**: Amazon Chronos-T5 foundation model (`bolt-tiny` → `large`)
- **EDI Entegrasyonu**: Geçmiş EDI tahminleriyle karşılaştırma ve birleştirme
- **Performans Metriği**: Son 3 hafta RMSE bazlı kaynak seçimi (`CHRONOS / EDI / HYBRID`)
- **Bias Düzeltme**: Horizon bazlı sistematik hata düzeltmesi
- **Sütun Tahmini Modu**: EDI sütun yakınsama serisi ile alternatif Chronos girdi modu

---

## Dosya Yapısı

```
rolling-forecast-w-chronos/
├── app.py                        ← Streamlit web arayüzü
├── main/
│   ├── orchestrator.py           ← Ana iş akışı koordinatörü
│   ├── chronos_forecaster.py     ← Chronos model entegrasyonu
│   ├── edi_processor.py          ← EDI veri işleme
│   ├── excel_data_loader.py      ← Excel veri yükleme
│   ├── stock_calculator.py       ← Stok karar motoru
│   ├── models.py                 ← Veri modelleri (dataclass)
│   ├── main.py                   ← CLI giriş noktası
│   ├── run_scenario_test.py      ← Senaryo test betiği
│   ├── requirements.txt
│   └── chronos_forecasts.json    ← Tahmin geçmişi (otomatik oluşur)
└── README.md
```

---

## Kurulum

```bash
pip install chronos-forecasting[training] torch numpy pandas openpyxl scipy
pip install streamlit plotly
```

> İlk çalıştırmada Chronos modeli otomatik indirilir (~100–500 MB, model boyutuna göre).

---

## Kullanım

### A) Streamlit Arayüzü (Önerilen)

```bash
cd rolling-forecast-w-chronos
streamlit run app.py --server.port 8501
```

Tarayıcı otomatik açılır: `http://localhost:8501`

**Arayüz Sekmeleri:**
| Sekme | İşlev |
|---|---|
| Haftalık Planlama | Tek hafta için tahmin ve karar üret |
| Simülasyon | Belirli hafta aralığında rolling forecast çalıştır |
| Hata Analizi | Horizon bazlı RMSE / Bias grafikleri |

**Sidebar Parametreleri:**
| Parametre | Açıklama |
|---|---|
| Excel Dosyası | `.xlsx` / `.xls` formatında veri dosyası |
| Material ID | Malzeme kodu (örn. `M100F133RO`) |
| Lead Time | Tedarik süresi (hafta) |
| Model Boyutu | `bolt-tiny` (hızlı) → `base` (doğru) |
| Sütun Tahmini | EDI sütun yakınsama modunu etkinleştirir |

---

### B) Komut Satırı (CLI)

**Tek hafta planlaması:**
```bash
python main/main.py --material-id M100F133RO --data data_safety_stock.xlsx --current-week 5 --lead-time 6
```

**Senaryo testi (hafta aralığı):**
```bash
cd main
python run_scenario_test.py --material-id M100F133RO --start-week 3 --end-week 12 --lead-time 6 --model-size bolt-base
```

**CLI Parametreleri:**
| Parametre | Varsayılan | Açıklama |
|---|---|---|
| `--material-id` | `M100F133RO` | Malzeme kodu |
| `--data` | `data_safety_stock.xlsx` | Veri dosyası yolu |
| `--model-size` | `bolt-base` | Chronos model boyutu |
| `--start-week` | `3` | Başlangıç haftası |
| `--end-week` | `12` | Bitiş haftası |
| `--lead-time` | `6` | Tedarik süresi (hafta) |
| `--use-column-forecast` | `False` | EDI sütun yakınsama modunu etkinleştirir |

---

## Model Boyutu Karşılaştırması

| Model | Hız | Doğruluk | Tavsiye |
|---|---|---|---|
| `bolt-tiny` | En hızlı | Düşük | İlk test |
| `bolt-base` | Orta | İyi | Genel kullanım |
| `small` | Yavaş | Daha iyi | Hassas analiz |
| `base` | En yavaş | En iyi | Üretim |

---

## Tahmin Kaynakları

| Kaynak | Açıklama |
|---|---|
| `CHRONOS` | Yalnızca Chronos tahmini kullanılır |
| `EDI` | Yalnızca EDI tahmin ortalaması kullanılır |
| `HYBRID` | Chronos + EDI performans ağırlıklı birleşim |
| `CHRONOS_COLUMN` | Sütun modunda Chronos |
| `HYBRID_COLUMN` | Sütun modunda hibrit |

---

## Önemli Notlar

- **Tahmin Geçmişi**: Gerçek zamanlı tahminler `main/chronos_forecasts.json` dosyasına kaydedilir
- **Veri Yükleme**: Arayüzde model ayarı değiştirildikten sonra **"Veriyi Yükle"** butonuna tekrar basılmalıdır
- **İlk Yükleme**: Orchestrator kurulumu 10–30 saniye sürebilir (model indirme dahil)
