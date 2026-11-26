import requests
from bs4 import BeautifulSoup
from datetime import datetime
import xml.etree.ElementTree as ET
import json
import os
import hashlib

# --- YAPILANDIRMA ---
NTFY_KANAL_ADI = "kpss-ist-678-ozel"
HAFIZA_DOSYASI = "hafiza.json"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
}

# --- KULLANICI PROFİL KURALLARI ---
HEDEF_SEHIR = "istanbul"
EGITIM = ["ortaöğretim", "lise", "p94", "meslek lisesi", "teknik lise"]
YUKSEK_PUAN_ENGEL = ["en az 70", "en az 75", "en az 80", "70 puan", "75 puan", "80 puan"]
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

def hafiza_yukle():
    if os.path.exists(HAFIZA_DOSYASI):
        with open(HAFIZA_DOSYASI, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def hafiza_kaydet(hafiza):
    with open(HAFIZA_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(hafiza[-500:], f, ensure_ascii=False, indent=2)

def id_olustur(metin):
    return hashlib.md5(metin.encode("utf-8")).hexdigest()

def ilan_analiz_et(baslik, icerik):
    tam_metin = f"{baslik} {icerik}".lower()
    if HEDEF_SEHIR not in tam_metin:
        return None
    if not any(k in tam_metin for k in EGITIM):
        return None
    if any(k in tam_metin for k in YUKSEK_PUAN_ENGEL):
        return None
    if any(k in tam_metin for k in ASKERLIK_ENGEL):
        return None
    if any(c in tam_metin for c in CINSIYET_ENGEL) and "erkek" not in tam_metin:
        return None

    bulunan_kategoriler = []
    for kat_adi, kelimeler in KATEGORILER.items():
        if any(k in tam_metin for k in kelimeler):
            if "Sofor" in kat_adi and any(a in tam_metin for a in AGIR_VASITA_ENGEL) and "b sınıfı" not in tam_metin:
                continue
            if "Guvenlik" in kat_adi and any(b in tam_metin for b in BOY_ENGEL):
                continue
            bulunan_kategoriler.append(kat_adi)

    if not bulunan_kategoriler:
        return None

    if any(v in tam_metin for v in VARDIYA_IPUCLARI):
        mesai = "UYARI: Vardiya / Gece / Hafta Sonu Riski"
    elif any(g in tam_metin for g in GUNDUZ_IPUCLARI):
        mesai = "Gunduz / Hafta Ici Mesaisi Yuksek Ihtimal"
    else:
        mesai = "Mesai Duzeni Ilan Detayinda Incelenmeli"

    return {"kategoriler": ", ".join(bulunan_kategoriler), "mesai": mesai}

def bildirim_gonder(baslik, mesaj, link, oncelik="high"):
    requests.post(
        f"https://ntfy.sh{NTFY_KANAL_ADI}",
        data=mesaj.encode("utf-8"),
        headers={
            "Title": baslik,
            "Priority": oncelik,
            "Click": link,
            "Tags": "rotating_light,briefcase" if oncelik == "high" else "white_check_mark"
        },
        timeout=15
    )

def kaynak_resmi_gazete(hafiza, rapor):
    bugun = datetime.now().strftime("%Y/%m/%d")
    url = f"https://resmigazete.gov.tr{bugun[:4]}/{bugun[5:7]}/{bugun.replace('/', '')}-4.htm"
    yeni_sayisi = 0
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.encoding = "utf-8"
        if r.status_code != 200:
            rapor.append("Resmi Gazete: Bugun henuz yayinlanmadi / Erisilemedi")
            return 0
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            baslik = a.get_text().strip()
            href = a["href"]
            if len(baslik) < 15:
                continue
            tam_link = href if href.startswith("http") else f"https://resmigazete.gov.tr{bugun[:4]}/{bugun[5:7]}/{href}"
            ilan_id = id_olustur(tam_link)
            if ilan_id in hafiza:
                continue
            detay = requests.get(tam_link, headers=HEADERS, timeout=15)
            detay.encoding = "utf-8"
            sonuc = ilan_analiz_et(baslik, detay.text)
            if sonuc:
                hafiza.append(ilan_id)
                yeni_sayisi += 1
                mesaj = f"[Resmi Gazete]\nIlan: {baslik}\nKategori: {sonuc['kategoriler']}\nDurum: {sonuc['mesai']}"
                bildirim_gonder("ISTANBUL KPSS ILANI (RESMI GAZETE)", mesaj, tam_link)
        rapor.append(f"Resmi Gazete: Aktif ({yeni_sayisi} yeni eslesme)")
    except Exception as e:
        rapor.append(f"Resmi Gazete: Hata ({str(e)[:30]})")
    return yeni_sayisi

def kaynak_google_kamu_xml(hafiza, rapor):
    sorgular = [
        "site:isealimkariyerkapisi.cbiko.gov.tr+istanbul+ortaöğretim",
        "site:kamuilan.sbb.gov.tr+istanbul+ortaöğretim",
        "site:iskur.gov.tr+istanbul+destek+personeli+OR+güvenlik+OR+şoför"
    ]
    yeni_sayisi = 0
    basarili_sorgu = 0
    for q in sorgular:
        rss_url = f"https://google.com{q}+when:2d&hl=tr&gl=TR&ceid=TR:tr"
        try:
            r = requests.get(rss_url, headers=HEADERS, timeout=15)
            if r.status_code == 200:
                basarili_sorgu += 1
                root = ET.fromstring(r.content)
                for item in root.findall(".//item"):
                    baslik = item.find("title").text or ""
                    link = item.find("link").text or ""
                    aciklama = item.find("description").text or ""
                    ilan_id = id_olustur(baslik)
                    if ilan_id in hafiza:
                        continue
                    sonuc = ilan_analiz_et(baslik, aciklama)
                    if sonuc:
                        hafiza.append(ilan_id)
                        yeni_sayisi += 1
                        mesaj = f"[Kamu Portali]\nIlan: {baslik}\nKategori: {sonuc['kategoriler']}\nDurum: {sonuc['mesai']}"
                        bildirim_gonder("ISTANBUL KAMU ILANI YAKALANDI!", mesaj, link)
        except Exception:
            pass
    rapor.append(f"Kariyer Kapisi/SBB/ISKUR XML: {basarili_sorgu}/3 Akis Aktif ({yeni_sayisi} yeni)")
    return yeni_sayisi

if __name__ == "__main__":
    hafiza = hafiza_yukle()
    rapor_satirlari = []
    
    toplam_yeni = 0
    toplam_yeni += kaynak_resmi_gazete(hafiza, rapor_satirlari)
    toplam_yeni += kaynak_google_kamu_xml(hafiza, rapor_satirlari)
    
    hafiza_kaydet(hafiza)
    
    zaman = datetime.now().strftime("%d.%m.%Y %H:%M")
    durum_ozeti = "\n".join(rapor_satirlari)
    rapor_mesaji = f"Tarama Zamani: {zaman}\n{durum_ozeti}\nToplam Yeni Bildirim: {toplam_yeni}"
    bildirim_gonder("KPSS Bot Sistem Raporu", rapor_mesaji, "https://cbiko.gov.tr", oncelik="low")
