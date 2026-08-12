# Kurulum — Barış için (kendi GitHub'ına alma)

Bu, rakip eSIM firmalarının paket fiyatlarını haftalık otomatik toplayan ve bir
karşılaştırma dashboard'u üreten bir sistemdir. Aşağıdaki adımlarla **kendi GitHub
hesabında** sıfırdan çalıştırabilirsin. Detaylı teknik döküman: **`HANDOFF.md`**.

---

## Ne var elinde
- `collect.py` — 6 firmayı toplayan ana toplayıcı (sadece Python stdlib, `pip install` yok)
- `collect_js.py` — 2 firma daha (Nomad, Saily — **beta**), Playwright ile
- `build_dashboard.py` → `docs/index.html` (dashboard) · `build_history.py` → `docs/history.json` (trend)
- `should_collect.py` + `events.json` — etkinliğe yakın sıklaştırma
- `.github/workflows/` — 2 otomatik iş (ana + JS)
- `data/` — mevcut fiyat anlık görüntüleri + `latest/` (dayanıklılık)
- `docs/` — üretilmiş dashboard (GitHub Pages bunu yayınlar)

---

## Adım adım kurulum

### 1) GitHub'da repo aç ve dosyaları yükle
- github.com'da yeni repo: örn. `esim-price-monitor`. **Public seç** (ücretsiz GitHub Pages
  sadece public repolarda çalışır; veriler zaten kamuya açık rakip fiyatları).
- Bu klasördeki **tüm dosyaları** yükle. Terminalden (klasörün içinde):
  ```bash
  git init && git add . && git commit -m "initial"
  git branch -M main
  git remote add origin https://github.com/<KULLANICI-ADIN>/esim-price-monitor.git
  git push -u origin main
  ```

### 2) Actions'a yazma izni ver
- Repo → **Settings → Actions → General** → en altta **Workflow permissions** →
  **Read and write permissions** seç → **Save**. (Toplanan veriyi geri commit'leyebilmesi için.)

### 3) Ana toplayıcıyı elle bir kez çalıştır
- Repo → **Actions** → **"eSIM price collection"** → **Run workflow**. ~2-3 dk sürer,
  bitince `data/prices_<bugün>.csv` ve `docs/index.html` güncellenir.

### 4) Dashboard'u yayınla (GitHub Pages)
- **Settings → Pages** → Source: **Deploy from a branch** → Branch: **main** → Folder:
  **/docs** → Save. 1-2 dk sonra dashboard şu adreste açılır:
  `https://<KULLANICI-ADIN>.github.io/esim-price-monitor/`

### 5) (Opsiyonel) Nomad + Saily (beta) toplayıcısı
- **Actions** → **"eSIM JS collector (Playwright)"** → **Run workflow** (mode: `collect`).
  Bu iş Playwright + Chromium kurar (~11 dk). İki firmayı ekleyip dashboard'u günceller.
- Bu iki firma dashboard'da **"beta"** rozetiyle işaretli — veride ara sıra ufak eksik olabilir.

---

## Zamanlama (otomatik, kurulunca kendiliğinden çalışır)
- **Ana toplayıcı:** her Pazartesi 06:00 UTC (+ büyük etkinliklere 7 gün kala günlük)
- **JS toplayıcı:** her Pazartesi 07:00 UTC
- Değiştirmek için: `.github/workflows/*.yml` içindeki `cron:` satırları.

## Önemli notlar
- **Bağımlılık yok** (ana toplayıcı): GitHub sadece Python 3.12 kurar, `pip install` gerekmez.
  (JS toplayıcı kendi workflow'unda Playwright'ı kurar.)
- **Airalo USD:** Airalo fiyatı sunucunun konumuna göre para birimi değiştirir; GitHub
  runner'ları ABD IP'sinden çıktığı için doğru USD gelir. ABD-dışı bir yerde çalıştırma.
- **Dayanıklılık:** bir firma bir çalışmada takılırsa son iyi verisi korunur (`data/latest/`);
  dashboard üstünde `⚠ stale` uyarısı çıkar.
- **Yeni etkinlik eklemek:** sadece `events.json`'u düzenle.
- Firma başına veri erişim yöntemleri, bakım ve sorun giderme → **`HANDOFF.md`**.

Sorun olursa `HANDOFF.md` her firmanın nasıl toplandığını ve nasıl tamir edileceğini anlatıyor.
