# Gelecekte Denemeye Değer Fikirler

## EDI Tahmin Birleştirme Yöntemleri

Şu an `get_edi_average_forecast` fonksiyonu sabit olarak **IQR + aritmetik ortalama** kullanıyor.
Aşağıdaki alternatifler, farklı talep yapılarında daha iyi sonuç verebilir.

---

### 1. Basit Medyan (`median`)

Tüm tahminleri sırala, ortadakini al. IQR gibi bir ön temizleme adımı gerektirmez.

**Ne zaman denenmeli:** Aykırı değer sayısı çok yüksekse veya veri dağılımı ağır kuyruklu (heavy-tailed) görünüyorsa. Hesaplaması basit, yorumlaması kolay.

---

### 2. IQR Temizle + Medyan (`iqr_median`)

IQR ile uç değerleri kestikten sonra ortalama yerine medyan al.

**Ne zaman denenmeli:** IQR temizleme sonrasında bile veri dağılımı çarpık (skewed) kalıyorsa. `iqr_mean`'e kıyasla aşırı büyük tek bir tahmin kalıntısını daha iyi bastırır.

---

### 3. Ağırlıklı Ortalama (`use_weighted`)

Son tahminlere doğru lineer artan ağırlık uygula:

```
weights = [1, 2, 3, ..., n]  # en eski → en yeni
```

**Ne zaman denenmeli:** Müşterinin sipariş planı sık güncelleniyorsa ve son tahminlerin gerçeğe daha yakın olduğu gözlemleniyorsa. Stabil talep yapılarında gereksiz gürültü getirebilir — önce `calculate_forecast_errors` ile horizon bazlı bias'a bakılması önerilir.

---

### Karşılaştırma Önerisi

Hangi yöntemin daha iyi çalıştığını anlamak için `calculate_source_accuracy` (RMSE) ile
aynı geçmiş veri üzerinde her yöntemi ayrı ayrı çalıştırıp karşılaştırmak yeterli olacaktır.
