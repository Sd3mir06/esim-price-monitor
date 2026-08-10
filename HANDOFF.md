# eSIM Fiyat İzleyici — Bulut Kurulum Devir Dökümanı (HANDOFF)

> Bu döküman, projeyi hiç bilmeyen **başka bir Claude hesabına** verilmek üzere yazılmıştır.
> Amaç: bu proje sıfırdan anlaşılabilsin ve **GitHub Actions + GitHub Pages** ile
> günlük çalışan bir bulut cron'una taşınabilsin. Adımları sırayla uygula.

---

## 0. Tek cümlede ne yapıyoruz

Bir eSIM şirketinin rakiplerinin **paket fiyatlarını her gün otomatik toplayıp** (ülke ×
paket bazında), sonuçları tarihli CSV olarak biriktiren ve tarayıcıda açılan bir
karşılaştırma **dashboard'u** üreten bir sistem. Şu an bir Mac'te `cron` ile çalışıyor;
onu **GitHub Actions**'a taşıyacağız ki her zaman açık olsun (Mac gerekmesin).

---

## 1. Şu anki durum (ne çalışıyor)

**6 rakipten veri toplanıyor** (hepsi herkese açık web sayfaları; login/ödeme yok):

| Rakip | Ülke | Erişim yöntemi |
|---|---|---|
| **Airalo** | ~216 | `airalo.com/{ülke}-esim` — fiyatlar sayfadaki `__NUXT_DATA__` JSON blob'unda |
| **Holafly** | ~413 | `esim.holafly.com/esim-{ülke}/` — HTML fiyat tablosu |
| **esim.io** | ~188 | `esim.io/destinations/esim-{ülke}` — plan kartları HTML'de |
| **Breeze** | ~200 | `breezesim.com/products.json` — Shopify katalog JSON'u |
| **PocketeSIM** | ~197 | `pocketesim.com/en/esim/{ülke}` — `data-esim*` HTML attribute'ları |
| **Ubigi** | ~167 | `cellulardata.ubigi.com/.../ubigi-esim-data-plans/` — **tek sayfada** tüm ülkeler, kart attribute'larında |

**3 rakipten toplanamıyor** (fiyatlar JavaScript/uygulama ile geliyor, ham HTML'de yok —
headless tarayıcı gerekir):
- **Nomad** (nomadesim.com) — JS SPA
- **Yesim** (yesim.app) — ülke sayfaları fiyatı JS ile yüklüyor
- **Simly** (simly.com) — SPA, fiyatları üçüncü parti `api-eu.glowingbud.com`'dan çekiyor

Günlük tam çıktı: ~13.000–13.500 paket satırı.

---

## 2. Dosya yapısı ve her dosyanın görevi

```
esim-price-monitor/
├── collect.py              # ANA TOPLAYICI. Tüm firmaları çeker → data/prices_YYYY-MM-DD.csv
├── build_dashboard.py      # En son CSV'den → docs/index.html (self-contained dashboard)
├── build_history.py        # Tüm dated CSV'leri → docs/history.json (trend grafikleri)
├── should_collect.py       # Kapı: bugün toplansın mı? (Pazartesi / etkinliğe yakın)
├── events.json             # Büyük küresel etkinlikler (isim, ülke, tarih, bayrak)
├── README.md               # Genel harita
├── HANDOFF.md              # (bu dosya)
├── .github/workflows/
│   └── collect.yml         # GÜNLÜK CRON (kapı ile Pazartesi/etkinlik'te toplar)
├── data/
│   ├── prices_YYYY-MM-DD.csv/json   # her çalışmanın anlık görüntüsü (geçmiş — silinmez)
│   └── latest/<Firma>.json          # her firmanın SON BAŞARILI verisi (carry-forward, §4)
└── docs/                    # YAYINLANAN çıktı — GitHub Pages buradan servis eder
    ├── index.html           # dashboard
    └── history.json         # trend grafiği verisi
```

**Önemli teknik gerçek:** `collect.py` ve `build_dashboard.py` **yalnızca Python standart
kütüphanesini** kullanır. `pip install` yoktur, `requirements.txt` yoktur. GitHub
Actions'ta sadece Python 3.12 kurup çalıştırmak yeterlidir.

**CSV kolon şeması** (`data/prices_*.csv`):
`date, competitor, country, data, days, price_usd, source_url`

---

## 3. Her firmanın veri erişim yöntemi (bakım için ayrıntı)

Bir firmanın sitesi değişirse `collect.py` içindeki ilgili parser'ı burayı okuyarak tamir et.

- **Airalo** — `parse_airalo(slug)`. Ülke listesi `sitemap-v2-countries.xml`'den (`{slug}-esim`).
  Fiyatlar sayfadaki `<script id="__NUXT_DATA__">` JSON dizisinde. Paket dict'leri
  `data / day / is_unlimited / price` alanlarına sahip; `price` bir index-pointer'dır,
  çözülünce `{amount, currency}` verir. Sesli+SMS paketleri (`voice`/`text` dolu) atlanır.
  **⚠ PARA BİRİMİ:** Airalo fiyatı, isteği yapan sunucunun **konumuna (geo-IP)** göre farklı
  para biriminde render eder. Parser'da bir **USD kilidi** var: `price.currency.code != "USD"`
  ise satır atlanır (bozuk veri girmesin). GitHub Actions runner'ları **ABD IP**'sinden çıktığı
  için Airalo doğru USD verir — sorun yok. Ama iş ABD-dışı bir sunucuda çalıştırılırsa Airalo
  0 satır döner ve **carry-forward** son iyi USD veriyi korur. (Diğer 5 firma her IP'den USD
  verdiği için etkilenmez.) Kısacası: **toplamayı ABD bölgeli bir runner'da çalıştır.**
- **Holafly** — `parse_holafly(slug)`. Ülke listesi `product-sitemap.xml`'den (`esim-{slug}`).
  Fiyat tablosu: `<th ...>N days</th> ... <span>$ 11.90</span>` deseni.
- **esim.io** — `parse_esimio(slug)`. Ülke listesi `esim.io/destinations` sayfasındaki
  `/destinations/esim-{slug}` linklerinden. Kartlar: `N GB ... N Days ... $fiyat`.
- **Breeze** — `collect_breeze()`. Shopify. `breezesim.com/products.json?page=N` sayfalanır.
  Handle `esim-{ülke}` olan ürünler; her varyant bir paket (`option1` = "3GB" veya
  "Unlimited Essential 3 Day", `price`). **429 (rate limit) verir** — bkz. §4.
- **PocketeSIM** — `parse_pocketesim(slug)`. Ülke listesi `pocketesim.com/en/esim`'den.
  Kartlar: `data-esimData="1 GB" data-esimValidity="7 Days" data-esimUnitPrice="2.99"`.
- **Ubigi** — `collect_ubigi()`. **Tek sayfa** tüm ülkeleri içerir. Kart attribute'ları:
  `data-iso="USA" data-plantype="COUNTRY" data-allowance="10" data-validity="30" data-price="14"`.
  ISO-3 → ülke adı eşlemesi `collect.py` içinde `ISO3` sözlüğünde (hardcoded).

---

## 4. Güvenilirlik mekanizmaları (SİLME/BOZMA)

Firmalar tek tek dönüşümlü takılabilir (özellikle Breeze `429`, ya da datacenter IP
blokları). Bunları çözmek için şu koruma katmanları var — bulut kurulumunda da kritik:

1. **Carry-forward (son iyi veriyi taşıma).** `collect.py`, her firmanın başarılı çıktısını
   `data/latest/{firma}.json`'a yazar. Bir firma o çalışmada **0 satır** dönerse, en son
   başarılı verisi (kendi orijinal tarihiyle) o günün dosyasına taşınır. Böylece dashboard
   asla bir firma için boş kalmaz. **GitHub Actions'ta bunun çalışması için `data/latest/`
   klasörünün repo'ya commit'lenip kalıcı olması gerekir** (workflow bunu yapıyor).
2. **429 retry.** `fetch()` ve `collect_breeze()`, 429 alınca artan beklemeyle tekrar dener.
3. **Bayatlık göstergesi.** `build_dashboard.py`, bir firmanın verisi en yeni tarihten
   eskiyse dashboard üstünde `⚠ stale (last good): Breeze 2026-07-26` uyarısı gösterir.
4. **(Eski Mac cron'unda) ağ-bekleme** `run.sh`'ta vardı; GitHub Actions'ta runner'ın ağı
   hazır olduğu için gerekmez.

---

## 5. GİTHUB ACTIONS'A TAŞIMA — ADIM ADIM

> Ön koşul: bir GitHub hesabı. Tüm adımlar ücretsiz. **Public repo öner** — çünkü (a)
> GitHub Pages ücretsiz Pages için public gerekir, (b) veriler zaten herkese açık rakip
> fiyatları. Gizlilik istenirse private repo + GitHub Pages için ücretli plan gerekir.

### Adım 1 — Repo oluştur ve dosyaları yükle
1. GitHub'da yeni bir repo aç: örn. `esim-price-monitor` (Public).
2. Bu klasördeki **tüm dosyaları** repo'ya koy: `collect.py`, `build_dashboard.py`,
   `README.md`, `HANDOFF.md`, `.github/workflows/collect.yml`, ve `data/` klasörü
   (**`data/latest/` dahil** — carry-forward için son iyi veriyi de taşı ki ilk günden
   dolu başlasın). `run.sh` opsiyonel (bulutta kullanılmaz).
   - CLI ile: `git init && git add . && git commit -m "initial" && git branch -M main &&
     git remote add origin <repo-url> && git push -u origin main`

### Adım 2 — Actions'ı etkinleştir ve elle bir kez çalıştır
1. Repo → **Settings → Actions → General** → "Allow all actions and reusable workflows"
   seçili olsun. Ayrıca **Workflow permissions** → **Read and write permissions** işaretli
   olsun (workflow'un veriyi geri commit'leyebilmesi için).
2. Repo → **Actions** sekmesi → "eSIM daily price collection" workflow'u → **Run workflow**
   (workflow_dispatch) ile elle tetikle.
3. Çalışmayı izle (~10 dk). Bitince repo'da yeni `data/prices_<bugün>.csv` ve güncellenmiş
   `dashboard.html` + `docs/index.html` commit'lenmiş olmalı.

### Adım 3 — GitHub Pages'i aç (dashboard'u yayınla)
1. Repo → **Settings → Pages**.
2. **Source: Deploy from a branch** → **Branch: `main`** → **Folder: `/docs`** → **Save**.
3. Birkaç dakika sonra dashboard şu adreste yayında olur:
   `https://<kullanıcı-adı>.github.io/<repo-adı>/`
   (Workflow her gün `dashboard.html`'i `docs/index.html`'e kopyalayıp commit'lediği için
   Pages otomatik güncellenir.)

### Adım 4 — Zamanlama (cron): TEST = GÜNLÜK, NORMAL = AYDA 1
`.github/workflows/collect.yml` içinde iki cron seçeneği var. **Şu an TEST aşamasındayız,
yani GÜNLÜK aktif** — böylece hataları hızlı görürüz (hangi firma takılıyor vb.):
```yaml
on:
  schedule:
    # TEST (aktif): her gün 06:00 UTC = 09:00 Türkiye
    - cron: "0 6 * * *"
    # NORMAL: ayda 1 (aşağıyı aç, yukarıyı sil)
    # - cron: "0 6 1 * *"    # her ayın 1'i, 06:00 UTC
```
**Test bitince aylığa geçiş:** üstteki günlük satırı sil, alttaki aylık satırın başındaki
`#`'i kaldır. Başka değişiklik gerekmez.

**Dürüst uyarı — aylık cadence'in etkisi:**
- Fiyatlar **en fazla 1 ay eski** olabilir (rakip fiyat değiştirirse bir sonraki ayki
  çalışmaya kadar görmezsin).
- Bir firma aylık çalışmada takılırsa **carry-forward** o firmanın **~1 ay önceki** verisini
  gösterir (dashboard'da `⚠ stale` uyarısıyla). Yani aylık düzende `stale` uyarısını takip
  etmek daha önemli.
- Bu yüzden **test aşamasını günlük tutmak değerli**: her firmanın parser'ının hâlâ
  çalıştığını ve bulut IP'sinin bloklanmadığını birkaç gün üst üste doğrula, sonra aylığa geç.

**Not:** GitHub Actions zamanlı işleri yoğunlukta birkaç dakika–birkaç saat gecikebilir;
normaldir. `workflow_dispatch` ile istediğin an elle de çalıştırabilirsin.

### Adım 5 — Doğrulama
- **Actions** sekmesinde günlük çalışmalar yeşil (başarılı) görünmeli.
- Her çalışmadan sonra yeni bir `data/prices_YYYY-MM-DD.csv` commit'i olmalı.
- Pages URL'i açıldığında 6 firma ve ~13.000 paket görünmeli. Üstte bir firma için
  `⚠ stale` uyarısı varsa o firma o gün takılmış ama eski verisi korunmuş demektir.

---

## 6. Riskler ve dikkat edilecekler (DÜRÜST UYARILAR)

- **Datacenter IP blokları.** GitHub Actions runner'ları bulut IP'lerinden çıkar. Bazı
  siteler (Airalo/Holafly/Ubigi vb.) bulut IP'lerini bloklayabilir veya rate-limit
  uygulayabilir → o firma `http=0/403/429` dönebilir. Bu durumda **carry-forward** eski
  veriyi korur (dashboard boş kalmaz) ama fiyatlar tazelenmez. Bir firma **günlerce üst
  üste `stale`** kalıyorsa: (a) `collect.py`'deki `UA` (User-Agent) başlığını güncel bir
  tarayıcınınkiyle değiştir, (b) gerekirse bir proxy ekle veya o firmayı **self-hosted
  runner**'da/başka ortamda çalıştır. Breeze (Shopify CDN) genelde bulutta sorunsuzdur.
- **Public repo = veriler herkese açık.** Rakip fiyatları zaten kamuya açık; sorun
  genelde yok. İç bilgi eklenecekse private repo'ya geç.
- **Actions dakika kotası.** Public repo'da sınırsız. Private repo'da aylık 2000 dk ücretsiz;
  günlük ~10 dk çalışma = ~300 dk/ay, rahat sığar.
- **Commit gürültüsü.** Her gün `dashboard.html` (~550 KB) ve CSV commit'lenir. Repo zamanla
  büyür ama yıllarca sorun olmaz. İstenirse eski `data/*.json` dosyaları periyodik temizlenebilir
  (CSV'ler kalsın).

---

## 7. Bakım ve sorun giderme

- **Bir firma sürekli 0 / stale.** Muhtemelen site HTML'i değişti veya IP bloğu. §3'teki
  ilgili parser'ı ve §6'yı uygula. Teşhis için o firmanın bir ülke URL'ini `curl -A "<UA>"`
  ile çekip fiyatların hâlâ HTML'de olup olmadığına bak.
- **Yeni rakip ekleme.** SSR (fiyat HTML'de) ise kolay: `collect.py`'ye bir `parse_X` +
  enumerasyon ekle, `PAGE_PROVIDERS`'a kaydet, `--providers` varsayılanına dahil et.
  SPA/JS ise headless tarayıcı (Playwright) gerekir.
- **Nomad / Yesim / Simly ekleme.** Bunlar JS ile fiyat yüklüyor. Playwright ile her ülke
  sayfasını render edip fiyatları okuyan ayrı bir modül gerekir; GitHub Actions'ta
  `playwright install chromium` adımı eklenmeli. İstenirse ayrı bir iş olarak planlanır.
- **Firma çıkarma.** `collect.py` `--providers` varsayılanından çıkar; `data/latest/`'taki
  dosyasını silersen dashboard'dan tamamen düşer.

---

## 8. NE DEĞİŞTİRME (bozmamak için)

- `data/latest/` klasörünü repo'dan silme — carry-forward buna dayanır.
- CSV kolon şemasını (`date,competitor,country,data,days,price_usd,source_url`) değiştirme —
  `build_dashboard.py` buna bağlı.
- `collect.py`'yi harici kütüphaneye bağımlı hale getirme — bulutta kurulum basitliğini
  bozar (şu an stdlib-only).
- Workflow'daki `permissions: contents: write` ve commit adımını kaldırma — yoksa veri
  geri yazılamaz.

---

## 9. Hızlı komut özeti (yerelde test için)

```bash
python3 collect.py                 # tüm firmalar, tüm ülkeler (~10 dk)
python3 collect.py --limit 5       # hızlı test: firma başına 5 ülke
python3 build_dashboard.py         # en son CSV'den dashboard.html üret
```

Bittiğinde `dashboard.html`'i tarayıcıda aç. Bulutta bunları workflow otomatik yapar.

## 10. Fiyat geçmişi & trend grafiği
- Her haftalık çalışma `data/prices_YYYY-MM-DD.csv` olarak **kalıcı** saklanır (silinmez) → fiyat geçmişi birikir.
- `build_history.py` tüm dated CSV'leri `docs/history.json`'a toplar; dashboard'daki **Price Trends / Fiyat Trendi** bölümü bunu çekip paket/plan/firma bazında zaman-serisi grafiği çizer.
- Grafik **canlı (Pages) adresinde** çalışır (history.json fetch edilir); `file://` ile açınca trend yüklenmez.
- Cron artık **HAFTALIK** (`0 6 * * 1`, Pazartesi). Her hafta grafiğe bir nokta eklenir.

## 11. Etkinlik takibi & yakın-dönem toplama
- `events.json` — büyük küresel etkinlikler (ülke, tarih aralığı, bayrak). Dashboard'da **Yaklaşan Etkinlikler** bölümü + tepede **canlı geri sayım** bunu kullanır (embed, offline çalışır).
- **Cron artık GÜNLÜK** (`0 6 * * *`) ama `should_collect.py` kapısı sadece şu durumlarda gerçekten toplar: (a) Pazartesi (haftalık taban), (b) bir etkinliğin başlangıcına **7 gün kala → bitişine kadar** (yakın takip). Diğer günler erken çıkar (ucuz no-op). Elle tetikleme (workflow_dispatch) her zaman toplar.
- Yeni etkinlik eklemek/çıkarmak: sadece `events.json`'u düzenle (isim en/tr, country = veri setindeki ülke adı, flag, start/end ISO, opsiyonel `approx:true`).
