# Stok Planlama Sistemi — Arayüz Geliştirme Notları

## Kurulum ve Başlatma

```bash
# Ek paketleri kur
pip install streamlit plotly

# Uygulamayı başlat
streamlit run app.py --server.port 8501
```

Tarayıcı otomatik açılır: `http://localhost:8501`

---

## Dosya Yapısı

```
rolling-forecast-w-chronos/
├── app.py                    ← Streamlit uygulaması (oluşturulacak)
├── main/
│   ├── orchestrator.py
│   ├── edi_processor.py
│   ├── chronos_forecaster.py
│   ├── stock_calculator.py
│   ├── models.py
│   └── chronos_forecasts.json
└── arayuz_baslat.md
```

---

## Geliştirme Notları

### A) Model Yüklemesi — `@st.cache_resource` Zorunlu

Streamlit her buton tıklamasında tüm Python dosyasını baştan çalıştırır.
Bu olmadan Chronos modeli her etkileşimde yeniden yüklenir (10–30 saniye beklersin).

```python
from main.orchestrator import StockPlanningOrchestrator

@st.cache_resource
def get_orchestrator():
    return StockPlanningOrchestrator(chronos_model_size="bolt-base")

orchestrator = get_orchestrator()
```

---

### B) Veri Kaybını Engelle — `st.session_state`

Excel yüklendikten sonra sayfa yenilenirse veri uçmasın diye.

```python
if "material_loaded" not in st.session_state:
    st.session_state.material_loaded = False
    st.session_state.material_id = None
```

---

### C) Excel Upload — Geçici Dosya Üzerinden

`st.file_uploader` disk yolu vermez, `BytesIO` verir.
`load_from_excel()` dosya yolu beklediği için geçici dosya gerekli.

```python
import tempfile

uploaded = st.file_uploader("Excel Dosyası", type=["xlsx", "xls"])
if uploaded:
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(uploaded.read())
        tmp_path = tmp.name
    orchestrator.load_material_data(tmp_path, material_id, lead_time)
```

---

### D) Uzun Hesaplamalar — `st.spinner`

`backfill_chronos_forecasts()` onlarca hafta için döngü çalıştırıyor.
`spinner` olmadan UI tamamen donmuş gibi görünür.

```python
with st.spinner("Tahminler hesaplanıyor..."):
    decision = orchestrator.run_weekly_planning(material_id, week)
st.success("Tamamlandı!")
```

---

### E) Print Çıktıları — Terminale Değil UI'ye Yansıt

`orchestrator.py` içindeki `print()` satırları Streamlit'te görünmez, sadece terminale gider.
Bu yöntemle tüm loglar arayüzde gösterilir.

```python
import io, sys

buf = io.StringIO()
sys.stdout = buf

decision = orchestrator.run_weekly_planning(material_id, week)

sys.stdout = sys.__stdout__

with st.expander("İşlem Logları"):
    st.code(buf.getvalue())
```

---

### F) `chronos_forecasts.json` Dosya Yolu

Şu an `edi_processor.py` içinde yol sabit: `"chronos_forecasts.json"`
Bu, çalışma dizinine (cwd) göre değişir. Streamlit farklı yerden çalışırsa
dosya yanlış konuma yazılır ya da bulunamaz.

```python
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FORECASTS_PATH = os.path.join(BASE_DIR, "main", "chronos_forecasts.json")
```

---

### G) Önerilen Ekran Yapısı

#### Sidebar
| Bileşen | Streamlit Widget |
|--------|-----------------|
| Excel dosyası yükle | `st.file_uploader` |
| Malzeme ID seç | `st.selectbox` |
| Lead time (hafta) | `st.number_input` |
| Chronos model boyutu | `st.selectbox` → bolt-tiny / bolt-base vb. |

#### Tab 1 — Haftalık Planlama
- Mevcut hafta seç (`st.slider` veya `st.number_input`)
- Çalıştır butonu
- Sonuç kartı: kaynak (HYBRID / EDI / CHRONOS), ham tahmin, düzeltilmiş tahmin
- RMSE karşılaştırması: Chronos vs EDI

#### Tab 2 — Simülasyon
- Başlangıç / bitiş haftası
- Çalıştır butonu
- Tüm haftalar tablosu (`st.dataframe`)
- Forecast vs Actual çizgi grafiği (Plotly)

#### Tab 3 — Hata Analizi
- Horizon bazlı RMSE bar chart (Plotly)
- Bias tablosu
