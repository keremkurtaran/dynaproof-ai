from flask import Flask, request, render_template_string, redirect, url_for
import datetime, csv, json, uuid, os, random, re, pandas as pd
from collections import Counter
import logging
from difflib import SequenceMatcher
import unicodedata
from fractions import Fraction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, "defter.csv")
STUDENT_FILE = os.path.join(BASE_DIR, "ogrenciler.json")

print(f"--> Dosyalar şuraya kaydediliyor: {BASE_DIR}")

def verileri_yukle():
    """Hata korumalı veri yükleme fonksiyonu"""
    # 1. JSON Kontrolü
    students = {}
    if os.path.exists(STUDENT_FILE):
        try:
            with open(STUDENT_FILE, encoding="utf-8-sig") as f:
                content = f.read().strip()
                if content: # Dosya boş değilse yükle
                    students = json.loads(content)
        except (json.JSONDecodeError, ValueError):
            print("UYARI: JSON dosyası bozuktu, otomatik sıfırlandı.")
            students = {} # Hata varsa boş sözlükle devam et
        except Exception as e:
            print(f"KRİTİK HATA (JSON): {e}")
            students = {}

    # 2. CSV Kontrolü (Yoksa başlıkları oluştur)
    if not os.path.exists(CSV_FILE):
        try:
            headers = ["zaman", "uid", "ad_soyad", "sinif", "soru", "cevap", "puan", "zorluk", "soru_no", "geri_bildirim"]
            pd.DataFrame(columns=headers).to_csv(CSV_FILE, index=False, encoding="utf-8-sig")
        except PermissionError:
            print("!!! HATA: defter.csv dosyası Excel'de açık olabilir. Lütfen kapatın!")

    return students

# Program başlarken verileri bir kere kontrol et
verileri_yukle()
# ============= 7. SINIF AKADEMİK BAŞARI TESTİ SORU HAVUZU (2018 MÜFREDAT) =============
# Kazanımlar: M.7.1.3 RASYONEL SAYILARLA İŞLEMLER, M.7.2.1. CEBİRSEL İFADELER, M.7.2.2. EŞİTLİK VE DENKLEM
SORU_SABLONLARI = {
    "rasyonel": { # M.7.1.3 RASYONEL SAYILARLA İŞLEMLER
        "temel": [
            "Bir rasyonel sayının toplama işlemine göre tersi ile çarpma işlemine göre tersinin toplamının {p1} olduğunu göster. (p1 bir tam sayı olsun)",
            "(-{p1}/{p2}) + ({p3}/{p4}) işleminin sonucunun neden {p5} olduğunu adım adım açıkla."
        ],
        "orta": [
            "Bir rasyonel sayının karesinin daima pozitif olduğunu, {p1}/{p2} örneği üzerinden ispatla.",
            "Rasyonel sayılarda çarpma işleminin toplama işlemi üzerine dağılma özelliğini, {p1}/{p2} * ({p3}/{p4} + {p5}/{p6}) örneği ile göster."
        ],
        "ileri": [
            "Bir rasyonel sayının 0'a olan uzaklığının (mutlak değerinin) daima pozitif olduğunu, -{p1}/{p2} örneği ile ispatla.",
            "İki rasyonel sayının toplamının rasyonel olduğunu, genel rasyonel sayı tanımını kullanarak göster."
        ]
    },

}

if not os.path.exists(CSV_FILE):
    headers = ["zaman", "uid", "ad_soyad", "sinif", "soru", "cevap", "puan", "zorluk", "soru_no", "geri_bildirim"]
    pd.DataFrame(columns=headers).to_csv(CSV_FILE, index=False, encoding="utf-8-sig")

# ============= AKILLI PUANLAMA SİSTEMİ (7. SINIF AKADEMİK BAŞARI ODAKLI) =============
def turkce_karakter_temizle(metin):
    """
    Türkçe karakterleri (ş, ğ, ü, ö, ç, ı) İngilizce karşılıklarına çevirir.
    Böylece 'hipotenüş' yazsa bile 'hipotenus' ile eşleşir.
    """
    return ''.join(c for c in unicodedata.normalize('NFD', metin)
                  if unicodedata.category(c) != 'Mn')

def puanla_akilli(ogrenci_cevabi, soru_metni):
    # 1. Temizlik ve Normalizasyon
    cevap_orijinal = ogrenci_cevabi.lower().strip()
    cevap_norm = turkce_karakter_temizle(cevap_orijinal)
    
    # Cevap yoksa
    if not cevap_norm or len(cevap_norm) < 3:
        return {
            "toplam": 0, "seviye": "cevap_yok", "max_puan": 100, 
            "geri_bildirim": "Henüz bir cevap yazmadın."
        }

    puan = 0
    # --- 1. ÇABA PUANI (20 Puan) ---
    puan += 20 

    # --- 2. MATEMATİKSEL TERİM PUANI (60 Puan) ---
    
    # Konuya göre anahtar kelimeler
    rasyonel_kelimeler = ["payda", "pay", "esitle", "genislet", "sadelestir", "kesir", "tam sayi", "toplam", "cikar", "bolum"]
    cebir_kelimeler = ["degisken", "bilinmeyen", "x", "katsayi", "terim", "benzer", "parantez", "dagilma"]
    mantik_kelimeler = ["cunku", "bu yuzden", "dolayi", "esittir", "sonuc", "elde edilir", "yani"]
    
    # Eskiden kalan geometri kelimeleri
    geo_kelimeler = ["hipotenus", "pisagor", "dik", "kare"]

    tum_kelimeler = rasyonel_kelimeler + cebir_kelimeler + mantik_kelimeler + geo_kelimeler
    
    bulunan_kelimeler = []
    
    for k in tum_kelimeler:
        if k in cevap_norm:
            bulunan_kelimeler.append(k)
        else:
            for kelime in cevap_norm.split():
                if SequenceMatcher(None, k, kelime).ratio() > 0.80:
                    bulunan_kelimeler.append(k)
                    break
    
    benzersiz_kelime_sayisi = len(set(bulunan_kelimeler))
    
    if benzersiz_kelime_sayisi >= 1: puan += 20
    if benzersiz_kelime_sayisi >= 3: puan += 20
    if benzersiz_kelime_sayisi >= 5: puan += 20

    # --- 3. MANTIK VE UZUNLUK PUANI (20 Puan) ---
    if len(cevap_norm.split()) > 5: 
        puan += 10
    if "cunku" in cevap_norm or "yuzden" in cevap_norm or "icin" in cevap_norm:
        puan += 10

    # Maksimum Puan Kontrolü
    if puan > 100: puan = 100

    # --- Geri Bildirim Oluşturma (Geliştirilmiş) ---
    
    # Detaylı geri bildirim için ipuçları
    eksik_terimler = [k for k in rasyonel_kelimeler if k not in cevap_norm]
    
    if puan >= 85:
        seviye = "mükemmel"
        mesaj = "Mükemmel! Matematiksel dil ve mantık yürütme becerin çok yüksek. Devam et!"
    elif puan >= 65: # Hassaslaştırılmış eşik
        seviye = "iyi"
        mesaj = "Çok iyi! Mantık yürütmen doğru ancak daha fazla matematiksel terim kullanabilirsin. Cevabını daha resmi bir dille yazmayı dene."
    elif puan >= 40:
        seviye = "orta"
        mesaj = f"Gelişmekte. Cevabında {' '.join(bulunan_kelimeler)} gibi terimler var. Ancak daha fazla adım ve sebep-sonuç ilişkisi kurmalısın. Özellikle rasyonel sayılarla ilgili şu terimleri kullanmayı dene: {', '.join(eksik_terimler[:3])}."
    else:
        seviye = "yetersiz"
        mesaj = "Yetersiz. Cevabını adım adım, matematiksel terimler (payda, pay, eşitleme) kullanarak ve 'çünkü' ile sebep belirterek tekrar yazmalısın."

    return {
        "toplam": int(puan),
        "seviye": seviye,
        "max_puan": 100,
        "geri_bildirim": mesaj
    }
# ============= MATEMATİK MOTORU (HATASIZ SORU ÜRETİCİSİ) =============
def rasyonel_soru_uret_motoru():
    """Python ile hatasız rasyonel sayı sorusu üretir (Toplama, Çıkarma, Çarpma, Bölme dahil)"""
    payda_limit = 12 
    islemler = ['+', '-', '*', '/']
    semboller = {'+': 'toplama', '-': 'çıkarma', '*': 'çarpma', '/': 'bölme'}
    
    while True:
        op = random.choice(islemler)
        s1 = Fraction(random.randint(-5, 5), random.randint(2, 6))
        s2 = Fraction(random.randint(-5, 5), random.randint(2, 6))
        
        # 0 olmasın
        if s1 == 0: s1 = Fraction(1, 2)
        if s2 == 0: s2 = Fraction(1, 3)

        # İşlemi yap
        if op == '+': 
            sonuc = s1 + s2
        elif op == '-': 
            sonuc = s1 - s2
        elif op == '*': 
            sonuc = s1 * s2
        elif op == '/': 
            # Bölme işleminde bölen 0 olmamalı
            if s2 == 0: continue
            sonuc = s1 / s2
        
        # Filtre: Sonuç çok karışık olmasın (payda limiti ve pay limiti)
        if sonuc.denominator <= payda_limit and -10 <= sonuc.numerator <= 10:
            
            # Soru Metni Oluştur
            soru = f"({s1}) {op} ({s2}) işleminin sonucunun neden {sonuc} olduğunu adım adım açıkla."
            return soru
# =====================================================================
# ============= AKILLI SORU ÜRETİMİ =============
def zorluk_belirle_akilli(profil: dict) -> str:
    """Öğrenci performansına göre zorluk seviyesi belirler"""
    puanlar = profil.get("gecmis_puanlar", [])
    
    if not puanlar:
        return "temel"
    
    # Son 3 sorunun ortalaması
    son_3 = puanlar[-3:] if len(puanlar) >= 3 else puanlar
    ortalama = sum(son_3) / len(son_3)
    max_puan = 100  # Düzeltildi: 100 üzerinden puanlama
    
    # Yüzdelik performans
    yuzde = (ortalama / max_puan) * 100
    
    # Trend analizi (yükseliyor mu düşüyor mu?)
    if len(puanlar) >= 2:
        trend = puanlar[-1] - puanlar[-2]
    else:
        trend = 0
    
    # Dinamik zorluk belirleme (Hassaslaştırılmış Eşikler)
    if yuzde >= 85 and trend >= 0: # %85 ve üzeri (Daha zorlayıcı eşik)
        return "ileri"
    elif yuzde >= 65 and trend >= -1: # %65 ve üzeri (Daha zorlayıcı eşik)        
        return "orta"
    else: # %65 altı
        return "temel"

def soru_uret_akilli(profil: dict) -> str:
    """Öğrencinin geçmiş performansına göre adaptif ve özgün soru üretir"""
    
    # 1. Zorluk seviyesini belirle
    zorluk_seviyesi = zorluk_belirle_akilli(profil)
    
    # 2. Daha önce sorulan soruları al
    gecmis_sorular = profil.get("gecmis_sorular", [])
    
    # 3. Konu Seçimi
    # Sadece Rasyonel Sayılar konusunu seç
    konu = "rasyonel"

    soru_metni = ""
    
    # --- YENİLİK BURADA: Rasyonel Sayı ise Motoru Kullan ---
    if konu == "rasyonel":
        # Matematik motorundan %100 doğru soru al
        soru_metni = rasyonel_soru_uret_motoru()
        
    else:
        # Diğer konular (Cebir, Denklem) için eski şablon sistemini kullan
        # Bu blok, sadece rasyonel sayılarla çalıştığımız için teoriktir.
        sablonlar = SORU_SABLONLARI[konu][zorluk_seviyesi]
        deneme_sayisi = 0
        while not soru_metni and deneme_sayisi < 10:
            sablon = random.choice(sablonlar)
            try:
                # Parametreleri doldur
                p1 = random.randint(2, 10)
                p2 = random.randint(2, 10)
                soru_metni = sablon.format(p1=p1, p2=p2, p3=random.randint(2,10), p4=random.randint(2,10), p5=random.randint(2,10), p6=random.randint(2,10))
            except:
                deneme_sayisi += 1
                continue
            
            # Soru tekrar kontrolü
            if any(s['soru'] == soru_metni for s in gecmis_sorular):
                soru_metni = ""
                deneme_sayisi += 1
            else:
                break

    # Eğer hala soru yoksa (Hata durumunda yedek)
    if not soru_metni:
        soru_metni = "1/2 + 1/3 işleminin sonucunu adım adım açıkla."

    # Soru numarasını kontrol et
    soru_no = profil.get("soru_sayisi", 0) + 1
    if soru_no > 10:
        return "UYGULAMA_BITTI"
        
    # Yeni soruyu geçmişe ekle
    profil["gecmis_sorular"].append({
        "soru_no": soru_no,
        "konu": konu,
        "zorluk": zorluk_seviyesi,
        "soru": soru_metni,
        "puan": 0 
    })
    
    return soru_metni
# ============= FLASK ROUTES =============
@app.route("/")
def index():
    return render_template_string("""
    <!doctype html>
    <html lang="tr">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>DynaProof – Giriş</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100% ); 
                min-height: 100vh; 
                display: flex;
                align-items: center;
            }
            .card { border-radius: 20px; box-shadow: 0 15px 35px rgba(0,0,0,0.3); }
            .logo { font-size: 3rem; margin-bottom: 10px; }
        </style>
    </head>
    <body>
        <div class="container" style="max-width:500px">
            <div class="card p-5">
                <div class="text-center logo">🎓</div>
                <h2 class="text-center mb-2">DynaProof</h2>
                <p class="text-muted text-center mb-4">Akıllı Öğrenme Sistemi</p>
                <form action="/basla" method="post">
                    <div class="mb-3">
                        <label class="form-label fw-bold">Adın</label>
                        <input class="form-control form-control-lg" name="ad" required placeholder="Örn: Ahmet">
                    </div>
                    <div class="mb-3">
                        <label class="form-label fw-bold">Soyadın</label>
                        <input class="form-control form-control-lg" name="soyad" required placeholder="Örn: Yılmaz">
                    </div>
                    <div class="mb-4">
                        <label class="form-label fw-bold">Sınıfın</label>
                        <select class="form-select form-select-lg" name="sinif">
                            <option value="7-A">7-A</option>
                            <option value="7-B">7-B</option>
                            <option value="7-C">7-C</option>
                            <option value="7-D">7-D</option>
                        </select>
                    </div>
                    <button class="btn btn-primary btn-lg w-100">Başla 🚀</button>
                </form>
            </div>
        </div>
    </body>
    </html>
    """)

@app.route("/basla", methods=["POST"])
def basla():
    ad = request.form.get("ad", "").strip()
    soyad = request.form.get("soyad", "").strip()
    sinif = request.form.get("sinif", "")
    
    if not ad or not soyad:
        return redirect(url_for("index"))
    
    uid = str(uuid.uuid4())[:8]
    students = {}
    if os.path.exists(STUDENT_FILE):
        with open(STUDENT_FILE, encoding="utf-8-sig") as f:
            students = json.load(f)
    
    students[uid] = {
        "ad": ad,
        "soyad": soyad,
        "sinif": sinif,
        "gecmis_puanlar": [],
        "gecmis_sorular": [], # Yeni eklendi
        "soru_sayisi": 0,
        "kayit_zamani": datetime.datetime.now().isoformat()
    }
    
    with open(STUDENT_FILE, "w", encoding="utf-8-sig") as f:
        json.dump(students, f, ensure_ascii=False, indent=2)
    
    return redirect(url_for("soru", uid=uid))

@app.route("/soru/<uid>")
def soru(uid):
    students = {}
    if os.path.exists(STUDENT_FILE):
        try:
            with open(STUDENT_FILE, encoding="utf-8-sig") as f:
                content = f.read().strip()
                if content:
                    students = json.loads(content)
        except:
            pass
    
    profil = students.get(uid)
    if not profil:
        return redirect(url_for("index"))
        
    if "gecmis_sorular" not in profil:
        profil["gecmis_sorular"] = []
    
    soru_no = profil.get("soru_sayisi", 0) + 1
    
    if soru_no > 10:
        return redirect(url_for("sonuc_ozet", uid=uid))
        
    # --- HATA DÜZELTME: SORU ÜRETİM KONTROLÜ ---
    gecmis_sorular = profil.get("gecmis_sorular", [])
    
    # Eğer hiç soru yoksa VEYA son soru numarası uyuşmuyorsa yeni soru üret
    if not gecmis_sorular or gecmis_sorular[-1]["soru_no"] != soru_no:
        soru_uret_akilli(profil)
        # Soru ürettikten sonra listeyi dosyaya kaydetmeyi unutma
        with open(STUDENT_FILE, "w", encoding="utf-8-sig") as f:
            json.dump(students, f, ensure_ascii=False, indent=2)
            
    # Garantilemek için tekrar oku (IndexError önlemi)
    if not profil["gecmis_sorular"]:
        return "Soru üretilemedi, lütfen sayfayı yenileyin."

    soru_bilgisi = profil["gecmis_sorular"][-1]
    soru_metni = soru_bilgisi["soru"]
    zorluk = soru_bilgisi["zorluk"]
    
    zorluk_renk = {"temel": "success", "orta": "warning", "ileri": "danger"}
    zorluk_emoji = {"temel": "🌱", "orta": "🌿", "ileri": "🌳"}
    
    # HTML şablonu (burası aynı kalacak, sadece yukarıdaki mantığı değiştirin)
    return render_template_string("""
    <!doctype html>
    <html lang="tr">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Soru {{soru_no}}</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100% ); min-height: 100vh; padding: 20px; }
            .card { border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
            .soru-box { 
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                border-left: 5px solid #667eea; 
                padding: 25px; 
                border-radius: 12px;
                font-size: 1.1rem;
            }
            textarea { font-size: 1rem; line-height: 1.8; }
            .ipucu-box { background: #fff3cd; border-left: 4px solid #ffc107; }
        </style>
    </head>
    <body>
        <div class="container" style="max-width:800px">
            <div class="card p-4 mb-3">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h5 class="mb-0">📝 Soru {{soru_no}}</h5>
                        <small class="text-muted">{{ad}} {{soyad}} - {{sinif}}</small>
                    </div>
                    <span class="badge bg-{{zorluk_renk}} px-3 py-2">
                        {{zorluk_emoji}} {{zorluk|title}}
                    </span>
                </div>
            </div>
            
            <div class="card p-4">
                <div class="soru-box mb-4">
                    <strong>{{soru}}</strong>
                </div>
                
                <form action="/cevap/{{uid}}" method="post">
                    <input type="hidden" name="soru_metni" value="{{soru}}">
                    <input type="hidden" name="soru_no" value="{{soru_no}}">
                    <input type="hidden" name="zorluk" value="{{zorluk}}">
                    
                    <div class="mb-3">
                        <label class="form-label fw-bold">Cevabın:</label>
                        <textarea class="form-control" name="cevap" rows="10" required 
                                  placeholder="Cevabını buraya yaz...

İyi bir cevap için:
1. Verilenlerle başla (örn: a = 5 için...)
2. İşlemleri adım adım yap
3. Her adımı açıkla (çünkü, bu yüzden...)
4. Somut sayılarla hesapla
5. Sonucu belirt (bulunmuştur, hesaplanmıştır)"></textarea>
                    </div>
                    
                    <div class="alert ipucu-box">
                        <strong>💡 İpucu:</strong>
                        <ul class="mb-0 mt-2">
                            <li>Matematiksel terimleri kullan (eşit, toplam, çift, tek...)</li>
                            <li>Somut sayılarla örnek ver</li>
                            <li>Sebep-sonuç ilişkisi kur (çünkü, bu yüzden...)</li>
                            <li>Cebirsel ifade kullan (a+b, n², ...)</li>
                            <li>Sonucunu net belirt</li>
                        </ul>
                    </div>
                    
                    <button class="btn btn-success btn-lg w-100">Gönder ve Değerlendir ✓</button>
                </form>
            </div>
        </div>
    </body>
    </html>
    """, uid=uid, soru=soru_metni, soru_no=soru_no, 
         ad=profil["ad"], soyad=profil["soyad"], sinif=profil["sinif"],
         zorluk=zorluk, zorluk_renk=zorluk_renk.get(zorluk, "primary"), 
         zorluk_emoji=zorluk_emoji.get(zorluk, "❓"))

@app.route("/cevap/<uid>", methods=["POST"])
def cevap(uid):
    cevap_metni = request.form.get("cevap", "").strip()
    soru_metni = request.form.get("soru_metni", "")
    soru_no = int(request.form.get("soru_no", 1))
    zorluk = request.form.get("zorluk", "temel")
    
    students = {}
    # Güvenli okuma
    if os.path.exists(STUDENT_FILE):
        try:
            with open(STUDENT_FILE, encoding="utf-8-sig") as f:
                content = f.read().strip()
                if content:
                    students = json.loads(content)
        except:
            students = {}
    
    profil = students.get(uid)
    if not profil:
        return redirect(url_for("index"))
        
    if "gecmis_sorular" not in profil:
        profil["gecmis_sorular"] = []
    
    # --- HATA DÜZELTME: LİSTE KONTROLÜ ---
    # Eğer geçmiş sorular listesi boşsa, puan verilecek bir soru yok demektir.
    # Kullanıcıyı yeni soru üretmesi için soru sayfasına yönlendir.
    if not profil["gecmis_sorular"]:
        return redirect(url_for("soru", uid=uid))
        
    # Akıllı puanlama
    sonuc = puanla_akilli(cevap_metni, soru_metni)
    
    # Son sorunun puanını geçmişe kaydet
    profil["gecmis_sorular"][-1]["puan"] = sonuc["toplam"]
    
    # Soru sayısını artır
    profil["soru_sayisi"] = profil.get("soru_sayisi", 0) + 1
    yeni_soru_no = profil["soru_sayisi"] + 1
    
    with open(STUDENT_FILE, "w", encoding="utf-8-sig") as f:
        json.dump(students, f, ensure_ascii=False, indent=2)
        
    # CSV Kaydı
    try:
        new_row = pd.DataFrame([{
            "zaman": datetime.datetime.now().strftime("%d-%m-%Y %H:%M"),
            "uid": uid,
            "ad_soyad": f"{profil.get('ad', '')} {profil.get('soyad', '')}",
            "sinif": profil.get('sinif', ''),
            "soru": soru_metni,
            "cevap": cevap_metni,
            "puan": sonuc["toplam"],
            "zorluk": zorluk,
            "soru_no": soru_no,
            "geri_bildirim": sonuc["geri_bildirim"].replace('\n', ' | ')
        }])
        
        # Dosya yoksa başlıklarla oluştur
        if not os.path.exists(CSV_FILE):
            new_row.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")
        else:
            new_row.to_csv(CSV_FILE, mode='a', header=False, index=False, encoding="utf-8-sig")
    except Exception as e:
        print(f"CSV Hatası: {e}")
    
    return redirect(url_for("sonuc", uid=uid, puan=sonuc["toplam"], 
                           seviye=sonuc["seviye"], soru_no=yeni_soru_no, 
                           max_puan=sonuc["max_puan"],
                           geri_bildirim=sonuc["geri_bildirim"]))

@app.route("/sonuc_ozet/<uid>")
def sonuc_ozet(uid):
    students = {}
    if os.path.exists(STUDENT_FILE):
        with open(STUDENT_FILE, encoding="utf-8-sig") as f:
            students = json.load(f)
    
    profil = students.get(uid)
    if not profil:
        return redirect(url_for("index"))
        
    # Geriye dönük uyumluluk için kontrol
    if "gecmis_sorular" not in profil:
        profil["gecmis_sorular"] = []
        
    gecmis_sorular = profil.get("gecmis_sorular", [])
    toplam_puan = sum(s['puan'] for s in gecmis_sorular)
    ortalama_puan = round(toplam_puan / len(gecmis_sorular), 1) if gecmis_sorular else 0
    max_puan = 100
    
    # Konu bazlı performans
    konu_performans = {}
    for s in gecmis_sorular:
        konu = s['konu']
        puan = s['puan']
        if konu not in konu_performans:
            konu_performans[konu] = {'toplam': 0, 'sayi': 0}
        konu_performans[konu]['toplam'] += puan
        konu_performans[konu]['sayi'] += 1
        
    konu_ozet = []
    for konu, data in konu_performans.items():
        konu_ozet.append({
            'konu': konu.capitalize(),
            'ortalama': round(data['toplam'] / data['sayi'], 1)
        })
        
    return render_template_string("""
    <!doctype html>
    <html lang="tr">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Uygulama Özeti</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100% ); min-height: 100vh; padding: 20px; }
            .card { border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
            .puan-box { font-size: 3.5rem; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container" style="max-width:700px">
            <div class="card p-5 text-center">
                <h2 class="mb-4">🎉 Tebrikler, Uygulama Bitti!</h2>
                <p class="lead"><strong>{{ profil['ad'] }} {{ profil['soyad'] }}</strong>, 10 soruluk akademik başarı testini tamamladın.</p>
                
                <div class="puan-box text-success mb-2">{{ ortalama_puan }}/{{ max_puan }}</div>
                <p class="text-muted mb-4">Ortalama Başarı Puanın</p>
                
                <h4 class="mb-3">Konu Bazlı Performansın</h4>
                <ul class="list-group mb-4">
                    {% for ozet in konu_ozet %}
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        {{ ozet['konu'] }}
                        <span class="badge bg-primary rounded-pill">{{ ozet['ortalama'] }}/{{ max_puan }}</span>
                    </li>
                    {% endfor %}
                </ul>
                
                <a href="/" class="btn btn-success btn-lg w-100">Yeni Oturum Başlat</a>
            </div>
        </div>
    </body>
    </html>
    """, profil=profil, ortalama_puan=ortalama_puan, max_puan=max_puan, konu_ozet=konu_ozet)

@app.route("/sonuc/<uid>")
def sonuc(uid):
    puan = int(request.args.get("puan", 0))
    max_puan = int(request.args.get("max_puan", 100))
    seviye = request.args.get("seviye", "")
    soru_no = int(request.args.get("soru_no", 1))
    geri_bildirim = request.args.get("geri_bildirim", "")
    
    students = {}
    if os.path.exists(STUDENT_FILE):
        with open(STUDENT_FILE, encoding="utf-8-sig") as f:
            students = json.load(f)
    
    profil = students.get(uid)
    if not profil:
        return redirect(url_for("index"))
        
    # Geriye dönük uyumluluk için kontrol
    if "gecmis_sorular" not in profil:
        profil["gecmis_sorular"] = []
    
    mesajlar = {
        "mükemmel": "🌟 Mükemmel! Harika bir ispat yazdın!",
        "iyi": "👏 Çok iyi! Birkaç küçük detay eksen mükemmel olacak!",
        "orta": "👍 İyi bir başlangıç! Biraz daha detay ekleyebilirsin!",
        "gelişmekte": "💪 Güzel çaba! Aşağıdaki önerileri dikkate al!",
        "yetersiz": "📚 Endişelenme! İpuçlarına bakarak tekrar deneyelim!"
    }
    
    renk = {
        "mükemmel": "success",
        "iyi": "info",
        "orta": "warning",
        "gelişmekte": "secondary",
        "yetersiz": "danger"
    }
    
    puanlar = profil["gecmis_puanlar"]
    ortalama = round(sum(puanlar) / len(puanlar), 1) if puanlar else 0
    yuzde = round((puan / max_puan) * 100)
    
    return render_template_string("""
    <!doctype html>
    <html lang="tr">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Sonuç</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { background: linear-gradient(135deg, #667eea 0%, #764ba2 100% ); min-height: 100vh; padding: 20px; }
            .card { border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
            .puan-box { font-size: 3.5rem; font-weight: bold; }
            .geri-bildirim-box { background: #f8f9fa; border-radius: 10px; padding: 20px; white-space: pre-line; }
            .progress { height: 25px; }
        </style>
    </head>
    <body>
        <div class="container" style="max-width:700px">
            <div class="card p-5 text-center">
                <div class="puan-box text-{{renk}} mb-2">{{puan}}/{{max_puan}}</div>
                <div class="mb-3">
                    <div class="progress">
                        <div class="progress-bar bg-{{renk}}" style="width: {{yuzde}}%">%{{yuzde}}</div>
                    </div>
                </div>
                <h4 class="mb-4">{{mesaj}}</h4>
                
                <div class="geri-bildirim-box text-start mb-4">
                    <h6 class="fw-bold mb-3">📋 Detaylı Geri Bildirim:</h6>
                    <div style="line-height: 2;">{{geri_bildirim}}</div>
                </div>
                
                <div class="row mb-4">
                    <div class="col-4">
                        <div class="bg-light p-3 rounded">
                            <div class="text-muted small">Soru</div>
                            <div class="h4 mb-0">{{soru_no}}</div>
                        </div>
                    </div>
                    <div class="col-4">
                        <div class="bg-light p-3 rounded">
                            <div class="text-muted small">Ortalama</div>
                            <div class="h4 mb-0">{{ortalama}}</div>
                        </div>
                    </div>
                    <div class="col-4">
                        <div class="bg-light p-3 rounded">
                            <div class="text-muted small">Seviye</div>
                            <div class="h6 mb-0">{{seviye|title}}</div>
                        </div>
                    </div>
                </div>
                
                {% if soru_no < 15 %}
                <a href="/soru/{{uid}}" class="btn btn-primary btn-lg w-100 mb-2">
                    Sonraki Soru →
                </a>
                <small class="text-muted">Seni seviyene uygun bir soru bekliyor! (Akademik Başarı Testi)</small>
                {% else %}
                <a href="/" class="btn btn-success btn-lg w-100">
                    Tebrikler! Yeni Oturum Başlat 🎉
                </a>
                {% endif %}
            </div>
        </div>
    </body>
    </html>
    """, puan=puan, max_puan=max_puan, yuzde=yuzde, seviye=seviye, 
         mesaj=mesajlar.get(seviye, ""), renk=renk.get(seviye, "secondary"), 
         soru_no=soru_no, uid=uid, ortalama=ortalama,
         geri_bildirim=geri_bildirim)
# ============= VERİ ANALİZİ VE RAPORLAMA =============
@app.route("/admin/rapor")
def admin_rapor():
    """Tüm öğrencilerin verilerini düzenli şekilde gösterir"""
    import pandas as pd
    from io import StringIO
    
    if not os.path.exists(CSV_FILE):
        return "Henüz veri yok!"
    
    # CSV'yi oku
    df = pd.read_csv(CSV_FILE, encoding='utf-8', on_bad_lines='skip', engine='python')
    
    # Öğrencilere göre grupla
    ogrenci_raporlari = []
    
    for uid in df['uid'].unique():
        ogrenci_df = df[df['uid'] == uid].sort_values('soru_no')
        
        if len(ogrenci_df) == 0:
            continue
        
        ilk_kayit = ogrenci_df.iloc[0]
        
        # Sorular ve cevaplar
        sorular_cevaplar = []
        for idx, row in ogrenci_df.iterrows():
            sorular_cevaplar.append({
                'soru_no': row['soru_no'],
                'zorluk': row['zorluk'],
                'soru': row['soru'],
                'cevap': row['cevap'][:200] + '...' if len(row['cevap']) > 200 else row['cevap'],
                'puan': row['puan'],
                'geri_bildirim': row['geri_bildirim']
            })
        
        # Öğrenci özet bilgileri
        ogrenci_raporlari.append({
            'ad_soyad': ilk_kayit['ad_soyad'],
            'sinif': ilk_kayit['sinif'],
            'giris_saati': ilk_kayit['zaman'],
            'toplam_soru': len(ogrenci_df),
            'ortalama_puan': round(ogrenci_df['puan'].mean(), 1),
            'en_yuksek_puan': ogrenci_df['puan'].max(),
            'en_dusuk_puan': ogrenci_df['puan'].min(),
            'sorular_cevaplar': sorular_cevaplar
        })
    
    return render_template_string("""
    <!doctype html>
    <html lang="tr">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Akademik Rapor - DynaProof</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; padding: 20px; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100% ); color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }
            .ogrenci-card { border: 2px solid #e0e0e0; border-radius: 10px; padding: 20px; margin-bottom: 30px; page-break-inside: avoid; }
            .soru-detay { background: #f8f9fa; border-left: 4px solid #667eea; padding: 15px; margin: 10px 0; border-radius: 5px; }
            .puan-badge { font-size: 1.2rem; font-weight: bold; padding: 5px 15px; border-radius: 20px; }
            table { font-size: 0.9rem; }
            .print-btn { position: fixed; top: 20px; right: 20px; z-index: 1000; }
            @media print {
                .print-btn, .no-print { display: none; }
                .ogrenci-card { page-break-inside: avoid; }
            }
        </style>
    </head>
    <body>
        <button class="btn btn-primary print-btn no-print" onclick="window.print()">🖨️ Yazdır / PDF</button>
        
        <div class="header text-center">
            <h1>📊 DynaProof Akademik Rapor</h1>
            <p class="mb-0">Öğrenci Performans Analizi ve Detaylı Değerlendirmeler</p>
            <small>Rapor Tarihi: {{ tarih }}</small>
        </div>
        
        <div class="container-fluid">
            <div class="alert alert-info no-print">
                <strong>📌 Rapor Bilgisi:</strong> Toplam {{ toplam_ogrenci }} öğrenci, {{ toplam_soru }} soru çözümü
            </div>
            
            {% for ogrenci in ogrenciler %}
            <div class="ogrenci-card">
                <div class="row mb-3">
                    <div class="col-md-8">
                        <h3>👤 {{ ogrenci.ad_soyad }}</h3>
                        <p class="text-muted mb-1">
                            <strong>Sınıf:</strong> {{ ogrenci.sinif }} | 
                            <strong>Giriş:</strong> {{ ogrenci.giris_saati }}
                        </p>
                    </div>
                    <div class="col-md-4 text-end">
                        <div class="mb-2">
                            <span class="badge bg-primary">{{ ogrenci.toplam_soru }} Soru</span>
                        </div>
                        <div>
                            <span class="puan-badge bg-success">Ort: {{ ogrenci.ortalama_puan }}/100</span>
                        </div>
                    </div>
                </div>
                
                <table class="table table-bordered table-sm">
                    <thead class="table-light">
                        <tr>
                            <th style="width: 5%">#</th>
                            <th style="width: 10%">Zorluk</th>
                            <th style="width: 30%">Soru</th>
                            <th style="width: 30%">Cevap</th>
                            <th style="width: 10%">Puan</th>
                            <th style="width: 15%">Değerlendirme</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for sc in ogrenci.sorular_cevaplar %}
                        <tr>
                            <td><strong>{{ sc.soru_no }}</strong></td>
                            <td>
                                {% if sc.zorluk == 'temel' %}
                                <span class="badge bg-success">🌱 Temel</span>
                                {% elif sc.zorluk == 'orta' %}
                                <span class="badge bg-warning">🌿 Orta</span>
                                {% else %}
                                <span class="badge bg-danger">🌳 İleri</span>
                                {% endif %}
                            </td>
                            <td><small>{{ sc.soru }}</small></td>
                            <td><small style="color: #555;">{{ sc.cevap }}</small></td>
                            <td class="text-center">
                                <strong class="text-primary">{{ sc.puan }}/100</strong>
                            </td>
                            <td><small style="color: #666;">{{ sc.geri_bildirim[:100] }}...</small></td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                
                <div class="row mt-3">
                    <div class="col-4">
                        <div class="alert alert-success mb-0 text-center">
                            <strong>En Yüksek</strong>  
{{ ogrenci.en_yuksek_puan }}/100
                        </div>
                    </div>
                    <div class="col-4">
                        <div class="alert alert-info mb-0 text-center">
                            <strong>Ortalama</strong>  
{{ ogrenci.ortalama_puan }}/100
                        </div>
                    </div>
                    <div class="col-4">
                        <div class="alert alert-warning mb-0 text-center">
                            <strong>En Düşük</strong>  
{{ ogrenci.en_dusuk_puan }}/100
                        </div>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
        
        <div class="text-center mt-5 mb-5">
            <a href="/admin/excel-indir" class="btn btn-success btn-lg no-print">📥 Excel Olarak İndir</a>
            <a href="/" class="btn btn-secondary btn-lg no-print">🏠 Ana Sayfa</a>
        </div>
    </body>
    </html>
    """, ogrenciler=ogrenci_raporlari, 
         toplam_ogrenci=len(ogrenci_raporlari),
         toplam_soru=sum(o['toplam_soru'] for o in ogrenci_raporlari),
         tarih=datetime.datetime.now().strftime("%d.%m.%Y %H:%M"))

@app.route("/admin/excel-indir")
def excel_indir():
    """Verileri düzenli Excel formatında indirir"""
    import pandas as pd
    from flask import send_file
    import io
    
    if not os.path.exists(CSV_FILE):
        return "Henüz veri yok!"
    
    # CSV'yi oku
    df = pd.read_csv(CSV_FILE, encoding='utf-8', on_bad_lines='skip', engine='python')
    
    # Excel writer oluştur
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # 1. Genel Özet Sayfası
        ozet_data = []
        for uid in df['uid'].unique():
            ogrenci_df = df[df['uid'] == uid]
            ilk_kayit = ogrenci_df.iloc[0]
            
            ozet_data.append({
                'Ad Soyad': ilk_kayit['ad_soyad'],
                'Sınıf': ilk_kayit['sinif'],
                'Giriş Saati': ilk_kayit['zaman'],
                'Toplam Soru': len(ogrenci_df),
                'Ortalama Puan': round(ogrenci_df['puan'].mean(), 1),
                'En Yüksek Puan': ogrenci_df['puan'].max(),
                'En Düşük Puan': ogrenci_df['puan'].min()
            })
        
        ozet_df = pd.DataFrame(ozet_data)
        ozet_df.to_excel(writer, sheet_name='Genel Özet', index=False)
        
        # 2. Detaylı Veriler Sayfası
        detay_df = df[['ad_soyad', 'sinif', 'zaman', 'soru_no', 'zorluk', 
                       'soru', 'cevap', 'puan', 'geri_bildirim']].copy()
        detay_df.columns = ['Ad Soyad', 'Sınıf', 'Zaman', 'Soru No', 'Zorluk', 
                           'Soru', 'Cevap', 'Puan', 'Geri Bildirim']
        detay_df.to_excel(writer, sheet_name='Detaylı Veriler', index=False)
        
        # 3. Her öğrenci için ayrı sayfa
        for uid in df['uid'].unique():
            ogrenci_df = df[df['uid'] == uid].copy()
            ad_soyad = ogrenci_df.iloc[0]['ad_soyad']
            
            # Sayfa adını temizle (Excel için)
            safe_name = ad_soyad.replace('/', '-')[:31]
            
            ogrenci_df_clean = ogrenci_df[['soru_no', 'zorluk', 'soru', 'cevap', 'puan', 'geri_bildirim']].copy()
            ogrenci_df_clean.columns = ['Soru No', 'Zorluk', 'Soru', 'Cevap', 'Puan', 'Geri Bildirim']
            ogrenci_df_clean.to_excel(writer, sheet_name=safe_name, index=False)
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'DynaProof_Rapor_{datetime.datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
    )
if __name__ == "__main__":
    print("\n" + "="*60)
    print("🚀 DynaProof - Gelişmiş Versiyon Başlatılıyor...")
    print("="*60)
    print("📍 Adres: http://127.0.0.1:5000" )
    print("⚠️  Durdurmak için: Ctrl+C")
    print("="*60 + "\n")
    app.run(debug=True, host='127.0.0.1', port=5001, use_reloader=False)
