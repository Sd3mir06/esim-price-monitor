# Fiyatlandırma & Kâr Motoru — Barış'tan İhtiyaçlar

Selam Barış 👋

Rakip eSIM fiyatlarını otomatik toplayan sistemimizin üstüne bir **fiyatlandırma / kâr
öneri motoru** kuruyoruz. Amaç: ülke ve paket bazında “şu fiyatı koyarsak rakiplere göre
kaçıncı sıradayız ve kârımız ne olur” sorusuna dinamik cevap veren bir ekran.

Bu motorun **arka planda akıllı çalışması** için senden birkaç veri lazım. Aşağıda ne
istediğimizi, **neden** istediğimizi ve **hangi formatta** vermenin işimizi göreceğini yazdım.
Excel/Sheets ya da düz tablo, fark etmez — aşağıdaki şablonları doldurman yeterli.

---

## 1) Sabit giderlerimiz — Telna ve eSIMgo (ayrı ayrı)

**Neden:** Bir paketin fiyatını önerebilmek için o paketin bize **gerçek maliyetini**
bilmemiz gerek. İki provider’ımız var (Telna, eSIMgo) ve maliyet modelleri farklı.

**İhtiyaç:** Her provider için paket/GB başına maliyet. Ülkeye göre değişiyorsa ülke bazında,
sabitse tek tablo yeterli.

| Provider | Ülke (veya "genel") | Veri | Süre | Bize maliyeti (USD) |
|---|---|---|---|---|
| Telna | United States | 5 GB | 30 gün | … |
| eSIMgo | United States | 5 GB | 30 gün | … |
| … | … | … | … | … |

> Not: Maliyet GB başına bir orandan mı hesaplanıyor (ör. $0.80/GB), yoksa paket paket sabit
> mi? Hangisiyse öyle ver — biz ona göre modelleriz.

---

## 2) Telna tüketim çarpanı + "kullanılmayan GB" tablosu

**Neden:** Telna’da kullanılmayan GB’yi ödemiyoruz — yani 5 GB’lik paket satsak da müşteri
ortalama 3 GB kullanıyorsa maliyetimiz 5 değil ~3 GB üzerinden oluyor. Bu, Telna’yı avantajlı
kılan şey ve motorun maliyeti doğru hesaplaması için şart.

**İhtiyaç:**
- **Tüketim çarpanı / oranı:** Satılan pakete göre ortalama gerçek tüketim ne? (ör. 5 GB
  paket → ortalama %60 tüketim → efektif maliyet 3 GB üzerinden.)
- Bahsettiğin **"kullanılmayan GB" tablosu** — elindeki haliyle gönderebilirsin.

| Paket boyutu | Ortalama tüketim (%) veya GB | Not |
|---|---|---|
| 1 GB | … | |
| 5 GB | … | |
| 10 GB | … | |
| Unlimited | … | |

---

## 3) Telna-tercih eşiği (%)

**Neden:** Tercihimiz **her zaman Telna** (yukarıdaki tüketim avantajı yüzünden). Ama eSIMgo
belli bir orandan fazla ucuzsa eSIMgo’ya geçmek isteyebiliriz. Motorun bu kararı otomatik
vermesi için bir eşik lazım.

**İhtiyaç:** eSIMgo, Telna’dan **en fazla yüzde kaç** ucuzsa yine Telna’da kalalım?

> Örnek: eşik = **%3** → eSIMgo maliyeti Telna’nın %3’ü içindeyse → Telna seçilir. Sadece
> %3’ten fazla ucuzsa eSIMgo’ya geçilir.
>
> **Senin belirlemen gereken tek sayı:** eşik = **____ %**

---

## 4) Diğer giderler (sosyal medya vb.)

**Neden:** Gerçek kârı hesaplarken sabit provider maliyetinin yanına pazarlama/operasyon
giderlerini de eklememiz gerek.

**İhtiyaç:** Bu giderler nasıl dağıtılıyor?
- [ ] **Satış başına** sabit bir tutar mı? (ör. her satışta ~$0.X)
- [ ] **Aylık toplam** mı? (o zaman tahmini aylık satış adedine böleriz)
- [ ] **Yüzde** mi? (satış fiyatının %X’i)

Kalemler (elindeki haliyle): sosyal medya, reklam, ödeme komisyonu, destek, vs. — hangileri
varsa ve tutarları.

---

## Özet — 4 şey lazım
1. **Sabit giderler** — Telna & eSIMgo, paket/GB başına (tablo 1)
2. **Telna tüketim çarpanı** + kullanılmayan-GB tablosu (tablo 2)
3. **Telna-tercih eşiği** — tek bir yüzde (bölüm 3)
4. **Diğer giderler** — tutar + nasıl dağıtıldığı (bölüm 4)

Bunlar gelince motoru canlıya bağlarız. Sorun olursa yaz, birlikte netleştiririz. Teşekkürler 🙏
