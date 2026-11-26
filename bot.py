import requests
from bs4 import BeautifulSoup
from datetime import datetime

# --- IPHONE NTFY KANAL ADINI BURAYA YAZ ---
NTFY_KANAL_ADI = "kpss-ist-678-ozel"

# --- SENİN KİŞİSEL PROFİLİN (SADECE İSTANBUL) ---
HEDEF_SEHIR = "istanbul"
EGITIM = ["ortaöğretim", "lise", "p94", "meslek lisesi", "teknik lise"]
YUKSEK_PUAN_ENGEL = ["en az 70", "en az 75", "en az 80", "70 puan almış", "75 puan almış", "80 puan almış"]
ASKERLIK_ENGEL = ["askerliğini yapmış olmak", "askerlik hizmetini fiilen tamamlamış", "fiilen yapmış olmak"]
CINSIYET_ENGEL = ["sadece kadın", "kadın personel alınacaktır", "kadın destek personeli", "bayan personel"]
AGIR_VASITA_ENGEL = ["d sınıfı", "e sınıfı", "de sınıfı", "ce sınıfı", "otobüs", "kamyon", "ağır vasıta"]
BOY_ENGEL = ["165 cm", "167 cm", "168 cm", "170 cm", "171 cm", "172 cm", "173 cm", "175 cm"]

KATEGORILER = {
    "Kalorifer / Atesci": ["kalorifer", "ateşçi", "katı ve sıvı", "doğalgaz yakıtlı", "ısıtma"],
    "Bilisim / Buro / Adliye": ["bilişim", "veri tabanı", "bilgisayar", "teknisyen", "2023", "6225", "büro personeli", "zabıt katibi", "mübaşir"],
    "B Ehliyet Sofor (5 Yil Uygun)": ["şoför", "b sınıfı", "sürücü belgesi"],
    "Havuz Operatoru": ["havuz suyu", "havuz operatörü", "hijyen"],
    "Ozel Guvenlik (Boy Sartsiz)": ["koruma ve güvenlik", "özel güvenlik", "silahlı"]
}

GUNDUZ_IPUCLARI = ["üniversite", "rektörlük", "adliye", "milli eğitim", "tapu", "nüfus", "il müdürlüğü", "mesai saatleri"]
VARDIYA_IPUCLARI = ["hastane", "sağlık bakanlığı", "kyk", "yurt", "7/24", "vardiyalı"]

def metin_kontrol(metin):
    metin = metin.lower()
    if HEDEF_SEHIR not in metin:
        return None
    if not any(k in metin for k in EGITIM):
        return None
    if any(k in metin for k in YUKSEK_PUAN_ENGEL):
        return None
    if any(k in metin for k in ASKERLIK_ENGEL):
        return None
    if any(c in metin for c in CINSIYET_ENGEL) and "erkek" not in metin:
        return None

    bulunan_kategoriler = []
    for kat_adi, kelimeler in KATEGORILER.items():
        if any(k in metin for k in kelimeler):
            if "Sofor" in kat_adi and any(a in metin for a in AGIR_VASITA_ENGEL) and "b sınıfı" not in metin:
                continue
            if "Guvenlik" in kat_adi and any(b in metin for b in BOY_ENGEL):
                continue
            bulunan_kategoriler.append(kat_adi)

    if not bulunan_kategoriler:
        return None

    if any(v in metin for v in VARDIYA_IPUCLARI):
        mesai_notu = "UYARI: Vardiya / Gece / Hafta Sonu Riski Olabilir"
    elif any(g in metin for g in GUNDUZ_IPUCLARI):
        mesai_notu = "Gunduz / Hafta Ici Mesaisi Yuksek Ihtimal"
    else:
        mesai_notu = "Mesai Duzeni Ilan Detayinda Incelenmeli"

    return {
        "kategoriler": ", ".join(bulunan_kategoriler),
        "mesai": mesai_notu
    }

def resmi_gazete_tara():
    bugun = datetime.now().strftime("%Y/%m/%d")
    url = f"https://resmigazete.gov.tr{bugun[:4]}/{bugun[5:7]}/{bugun.replace('/', '')}-4.htm"
    
    try:
        r = requests.get(url, timeout=15)
        r.encoding = "utf-8"
        if r.status_code != 200:
            return
        
        soup = BeautifulSoup(r.text, "html.parser")
        ilanlar = soup.find_all("a")
        
        for ilan in ilanlar:
            baslik = ilan.get_text().strip()
            link = ilan.get("href")
            if not link or len(baslik) < 15:
                continue
            
            tam_link = link if link.startswith("http") else f"https://resmigazete.gov.tr{bugun[:4]}/{bugun[5:7]}/{link}"
            detay_r = requests.get(tam_link, timeout=15)
            detay_r.encoding = "utf-8"
            sonuc = metin_kontrol(detay_r.text)
            
            if sonuc:
                mesaj = (
                    f"Ilan: {baslik}\n"
                    f"Kategori: {sonuc['kategoriler']}\n"
                    f"Durum: {sonuc['mesai']}\n"
                    f"Profil: Istanbul | Erkek | Boy 160 | Tecil Uygun | 5 Yil B Ehliyet"
                )
                iphone_bildirim_gonder(mesaj, tam_link)
    except Exception as e:
        print("Hata:", e)

def iphone_bildirim_gonder(mesaj, link):
    requests.post(
        f"https://ntfy.sh{NTFY_KANAL_ADI}",
        data=mesaj.encode("utf-8"),
        headers={
            "Title": "ISTANBUL ICIN SANA UYGUN KPSS ILANI!",
            "Priority": "high",
            "Click": link,
            "Tags": "rotating_light,briefcase"
        }
    )

if __name__ == "__main__":
    resmi_gazete_tara()
