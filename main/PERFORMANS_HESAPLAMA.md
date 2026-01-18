# Performans Karsilastirmasi Matematiksel Aciklama

## Temel Kural
**ONEMLI:** Performans hesaplamalarinda sadece `current_week`'ten ONCEKI gerçeklesmis verileri kullanabiliriz!
Target_week >= current_week olan tahminlerin dogruluğu henuz bilinmiyor.

---

## Ornek Senaryo: current_week = 10, lead_time = 4

Bu durumda:
- Tahmin edilecek hafta: 10 + 4 = **Hafta 14**
- Performans hesabi icin kullanilabilecek gerceklesen veriler: **Hafta 1-9** (current_week'ten once)

---

## 1. CHRONOS Performans Hesabi (Son 3 Hafta)

### Mantik:
current_week=10'da Chronos'un gecmis performansini olcmek icin:
- Son 3 hafta: Hafta 7, 8, 9'da yapilan tahminlere bakariz
- AMA sadece target_week < current_week (yani < 10) olan tahminleri degerlendiririz

### Hesaplama:
```
Hafta 7'de yapilan tahminler:
  - Hafta 8 tahmini vs Hafta 8 gercekleseni -> KULLANILABILIR (8 < 10)
  - Hafta 9 tahmini vs Hafta 9 gercekleseni -> KULLANILABILIR (9 < 10)
  - Hafta 10 tahmini -> KULLANILAMAZ (10 >= 10, henuz gerceklesmedi)
  - Hafta 11 tahmini -> KULLANILAMAZ (11 >= 10)

Hafta 8'de yapilan tahminler:
  - Hafta 9 tahmini vs Hafta 9 gercekleseni -> KULLANILABILIR (9 < 10)
  - Hafta 10 tahmini -> KULLANILAMAZ (10 >= 10)

Hafta 9'da yapilan tahminler:
  - Hafta 10 tahmini -> KULLANILAMAZ (10 >= 10)
  - Hafta 11 tahmini -> KULLANILAMAZ (11 >= 10)
```

### Chronos RMSE Formulu:
```
errors = [
    (Hafta7_Chronos_TahminW8 - Hafta8_Gerceklesen),
    (Hafta7_Chronos_TahminW9 - Hafta9_Gerceklesen),
    (Hafta8_Chronos_TahminW9 - Hafta9_Gerceklesen)
]

RMSE = sqrt(mean(errors^2))
```

---

## 2. EDI Performans Hesabi (Son 3 Hafta, Her Hafta Icin 2 Tahmin)

### Mantik:
current_week=10'da EDI'nin gecmis performansini olcmek icin:
- Son 3 haftanin gerceklesenleri: Hafta 7, 8, 9
- Her hafta icin o haftaya yapilmis SON 2 TAHMIN kullanilir
- Bu tahminler o haftadan ONCE yapilmis olmali

### Hesaplama:

**Hafta 7 icin (2 tahmin):**
```
- Hafta 5'ten Hafta 7'ye yapilan tahmin (horizon=2)
- Hafta 6'dan Hafta 7'ye yapilan tahmin (horizon=1)

Hatalar:
  error1 = EDI[5][7] - Actual[7]
  error2 = EDI[6][7] - Actual[7]
```

**Hafta 8 icin (2 tahmin):**
```
- Hafta 6'dan Hafta 8'e yapilan tahmin (horizon=2)
- Hafta 7'den Hafta 8'e yapilan tahmin (horizon=1)

Hatalar:
  error3 = EDI[6][8] - Actual[8]
  error4 = EDI[7][8] - Actual[8]
```

**Hafta 9 icin (2 tahmin):**
```
- Hafta 7'den Hafta 9'a yapilan tahmin (horizon=2)
- Hafta 8'den Hafta 9'a yapilan tahmin (horizon=1)

Hatalar:
  error5 = EDI[7][9] - Actual[9]
  error6 = EDI[8][9] - Actual[9]
```

### EDI RMSE Formulu:
```
errors = [error1, error2, error3, error4, error5, error6]
RMSE = sqrt(mean(errors^2))
```

---

## 3. Kaynak Secimi

```
IF Chronos_RMSE < EDI_RMSE:
    Secilen = "CHRONOS"
    Agirlik_Chronos = daha yuksek
ELSE:
    Secilen = "EDI"
    Agirlik_EDI = daha yuksek

# Hibrit modda agirlikli ortalama:
w_chronos = 1 / (Chronos_RMSE + epsilon)
w_edi = 1 / (EDI_RMSE + epsilon)

Final_Tahmin = (Chronos * w_chronos + EDI * w_edi) / (w_chronos + w_edi)
```

---

## 4. Neden Bu Yaklasim?

1. **Gercekci Simulasyon:** Gercek hayatta current_week zamaninda sadece gecmis verileri biliyoruz
2. **Adil Karsilastirma:** Her iki kaynak da ayni kosullarda degerlendirilir
3. **Horizon-1 ve Horizon-2:** EDI'de son 2 tahmin kullanilarak kisa vadeli tahmin kalitesi olculur
4. **Kaymayan Pencere:** Her current_week icin 3 haftalik sabit pencere kullanilir

---

## 5. CSV Veri Yapisi Hatirlatmasi

```
         Sutun 1  Sutun 2  Sutun 3  Sutun 4  ...
Satir 1    1       236     1802     2049     ...   <- Hafta 1: Gerceklesen=236, Tahminler=1802,2049...
Satir 2    2       NaN     1944     2194     ...   <- Hafta 2: Gerceklesen=1944, Tahminler=2194...
Satir 3    3       NaN     NaN      2141     ...   <- Hafta 3: Gerceklesen=2141
...

Diagonal (ayni satir-sutun): Gerceklesen degerler
Ust ucgen (sutun > satir): Tahminler
```

EDI[forecast_week][target_week] = Tahmin degeri
Actual[week] = Gerceklesen deger (diagonal)
