## 1) Son 3 Hafta RMSE Nasıl Hesaplanıyor?

Bu hesaplama edi_processor.py dosyasındaki calculate_source_accuracy fonksiyonunda yapılıyor:

### Son 3 Hafta RMSE Hesaplama Adımları:

Örnek: Current Week = 8 ise

**# Adım 1: Son 3 haftayı belirle**

**lookback_weeks **=** **3

**weeks **=** **range**(**max**(**1**, **8** **-** **3**), **8**)  **# [5, 6, 7]

**# Adım 2: Her hafta için tahmin vs gerçekleşen **karşılaştırması

**errors **=** []**

**# Hafta 5'te yapılan tüm tahminler:**

**# - Örnek: Hafta 5'te "Hafta 8 için 1800" demiş**

**# - Gerçek (Hafta 8): 1650**

**# - Hata: 1800 - 1650 = 150**

**errors.append(**150**)**

**# Hafta 6'da yapılan tüm tahminler:**

**# - Örnek: Hafta 6'da "Hafta 9 için 1700" demiş**

**# - Gerçek (Hafta 9): 1600**

**# - Hata: 1700 - 1600 = 100**

**errors.append(**100**)**

**# Hafta 7'de yapılan tüm tahminler:**

**# - Benzer şekilde...**

**# Adım 3: RMSE formülü**

**# errors = [150, 100, 80, -50, ...]**

**RMSE **=** sqrt(mean(errors²))**

**     **=** sqrt((**150²** **+** **100²** **+** **80²** **+** (**-**50**)² **+** ...) **/** n)

**     **=** sqrt((**22500** **+** **10000** **+** **6400** **+** **2500** **+** ...) **/** n)**

**     **=** **128.42**  **# Chronos için

**     **=** **360.07**  **# EDI için

Çıkarım: Chronos, son 3 haftada ortalama 128 birim hata yaparken, EDI 360 birim hata yapmış.

---

## 2) Karar: 1729.08 Nasıl Hesaplandı?

Bu hesaplama orchestrator.py'daki ağırlıklı ortalama formülüyle yapılıyor:

### Ağırlıklı Ortalama Hesaplama (Ters Ağırlıklandırma):

Temel Mantık: Hatası düşük olan kaynağa daha fazla güven, hatası yüksek olana daha az güven.

**# Veriler (terminalinizden)**

**chronos_rmse **=** **128.42

**edi_rmse **=** **360.07

**chronos_forecast **=** **1650.00**  **# (tahmin ediyorum)

**edi_forecast **=** **2000.00**      **# (tahmin ediyorum)

**# Adım 1: Her kaynak için ağırlık hesapla (Ters **oran)

**w_chronos **=** **1.0** **/** (**128.42** **+** **0.000001**) **=** **0.007788

**w_edi **=** **1.0** **/** (**360.07** **+** **0.000001**) **=** **0.002777

**# Adım 2: Toplam ağırlık**

**total_weight **=** **0.007788** **+** **0.002777** **=** **0.010565

**# Adım 3: Normalize edilmiş ağırlıklar (yüzde **olarak)

**chronos_weight_percent **=** **0.007788** **/** **0.010565** **=** **0.7371** **=** **73.71**%**

**edi_weight_percent **=** **0.002777** **/** **0.010565** **=** **0.2629** **=** **26.29**%**

**# Adım 4: Ağırlıklı ortalama**

**raw_forecast **=** (chronos_forecast × w_chronos **+** edi_forecast × w_edi) **/** total_weight**

**             **=** (**1650** × **0.007788** **+** **2000** × **0.002777**) **/** **0.010565

**             **=** (**12.85** **+** **5.55**) **/** **0.010565

**             **=** **18.40** **/** **0.010565

**             **=** **1729.08

Mantık:* Chronos daha az hatalı olduğu için (%73.71 ağırlık)

* EDI daha çok hatalı olduğu için (%26.29 ağırlık)
* Final tahmin, Chronos'a daha yakın (1729.08)

---

## 3) Bias, RMSE ve Std Nasıl Hesaplanıyor?

Bu hesaplamalar edi_processor.py'daki calculate_forecast_errors fonksiyonunda yapılıyor:

### Horizon Bazlı Hata Metrikleri (Bias, RMSE, Std):

Örnek: Horizon 1 için (1 hafta ileri tahminler)

**# Adım 1: Horizon 1'deki tüm tahmin-gerçek **çiftlerini topla

**errors **=** []**

**# Hafta 1'de Hafta 2 için yapılan tahmin:**

**# Tahmin: 1802, Gerçek: 1944 → Hata = 1802 - 1944 **= -142

**errors.append(**-**142**)

**# Hafta 2'de Hafta 3 için yapılan tahmin:**

**# Tahmin: 2194, Gerçek: 2141 → Hata = 2194 - 2141 **= +53

**errors.append(**53**)**

**# Hafta 3'te Hafta 4 için yapılan tahmin:**

**# Tahmin: 1372, Gerçek: 1661 → Hata = 1372 - 1661 **= -289

**errors.append(**-**289**)

**# ... ve benzeri diğer haftalar**

**# errors = [-142, 53, -289, 80, 100, -50, ...] **(örnek)

**# Adım 2: Bias (Ortalama Hata - Sistematik sapma)**

**bias **=** mean(errors)**

**     **=** (**-**142** **+** **53** **+** (**-**289**) **+** **80** **+** **100** **+** (**-**50**) **+** ...) **/** n

**     **=** **29.67

**# Pozitif Bias = 29.67 → Sistem genelde FAZLA **tahmin ediyor (over-forecast)

**# Negatif olsaydı → Az tahmin ediyor **(under-forecast)

**# Adım 3: RMSE (Root Mean Square Error - Toplam **hata büyüklüğü)

**rmse **=** sqrt(mean(errors²))**

**     **=** sqrt(((**-**142**)² **+** **53²** **+** (**-**289**)² **+** ...) **/** n)**

**     **=** sqrt((**20164** **+** **2809** **+** **83521** **+** ...) **/** n)**

**     **=** **192.94

**# RMSE yüksekse → Tahminler çok dağınık/tutarsız**

**# Adım 4: Std (Standard Deviation - Hataların **değişkenliği)

**# İlk önce bias'ı düzelt (hataların sapmasını ölç)**

**deviations **=** errors **-** bias**

**           **=** [**-**142**-**29.67**, **53**-**29.67**, **-**289**-**29.67**, ...]**

**           **=** [**-**171.67**, **23.33**, **-**318.67**, ...]**

**std **=** sqrt(**sum**(deviations²) **/** (n**-**1**))  **# ddof=1: örnek std**

**    **=** **199.13

**# Std yüksekse → Hataların dağılımı geniş **(belirsizlik yüksek)

### Özet Karşılaştırma:

| Metrik | Değer | Anlamı                                               |
| ------ | ------ | ----------------------------------------------------- |
| Bias   | +29.67 | Sistem ortalama 29.67 birim fazla tahmin ediyor       |
| RMSE   | 192.94 | Tahminlerin ortalama hata büyüklüğü 192.94 birim |
| Std    | 199.13 | Hataların değişkenliği/yayılması 199.13 birim   |

Pratik Kullanım:* Bias → Düzeltme için (Tahmin - Bias = Düzeltilmiş Tahmin)

* RMSE/Std → Emniyet stoğu hesabı için (belirsizlik ölçüsü)

## 📊 Sipariş Miktarı Hesaplama Süreci

### Adım 1: Ham Tahmin (Hibrit Ortalama)

**Ham Tahmin = 1645.80 (Chronos %73.71 + EDI %26.29)**

### Adım 2: Bias Düzeltmesi

**Bias **=** **29.67**  **# (Horizon 1 için, sistemin geçmişteki sapması)

**Düzeltilmiş Tahmin **=** Ham Tahmin **-** Bias**

**                   **=** **1645.80** **-** **29.67

**                   **=** **1616.13

Mantık: Sistem geçmişte ortalama 29.67 birim fazla tahmin etmiş, bunu düzeltiyoruz.

### Adım 3: Emniyet Stoğu Hesaplama

**# Servis seviyesi: %95 (Z = 1.645)**

**# RMSE: 192.94 (belirsizlik ölçüsü)**

**Safety Stock **=** Z × RMSE**

**             **=** **1.645** × **199.13**  **# (Std kullanılıyor)

**             **=** **327.53

Mantık: %95 olasılıkla stok tükenmemesi için yedek stok.

### Adım 4: Reorder Point (Yeniden Sipariş Noktası)

**Reorder Point **=** Düzeltilmiş Tahmin **+** Emniyet Stoğu**

**              **=** **1616.13** **+** **327.53

**              **=** **1943.66

Mantık: Bu seviyenin altına düşersek sipariş vermeliyiz.

### Adım 5: Sipariş Miktarı

**Mevcut Stok **=** **0.00

**Sipariş Miktarı **=** Reorder Point **-** Mevcut Stok**

**                **=** **1943.66** **-** **0.00

**                **=** **1943.66

## 🎯 Neden Bu Miktar?

Sistem şu mantıkla çalışıyor:

| Bileşen               | Değer  | Amacı                                      |
| ---------------------- | ------- | ------------------------------------------- |
| Düzeltilmiş Tahmin   | 1616.13 | Gerçek talebi karşılamak için           |
| Emniyet Stoğu         | 327.53  | Belirsizliğe karşı koruma (%95 güvence) |
| TOPLAM (Reorder Point) | 1943.66 | İdeal stok seviyesi                        |
| Mevcut Stok            | 0.00    | Elimizde hiç yok                           |
| Eksik                  | 1943.66 | Bu kadar sipariş ver                       |

### Eğer Mevcut Stok Farklı Olsaydı:

Örnek 1: Mevcut Stok = 500

**Sipariş Miktarı = 1943.66 - 500 = 1443.66**
