import re
import numpy as np
import streamlit as st
from PIL import Image
import easyocr

# Sayfa ayarları (Mobil uyumlu tasarım)
st.set_page_config(page_title="VBG Klinik Asistan", page_icon="🩺", layout="centered")

@st.cache_resource
def load_ocr():
    return easyocr.Reader(['tr', 'en'], gpu=False)

reader = load_ocr()

# Session State (Okunan değerleri hesaplayıcıya aktarmak için)
if "son_veriler" not in st.session_state:
    st.session_state["son_veriler"] = {}

REFERANSLAR = {
    "pH": {"min": 7.31, "max": 7.41, "kritik_alt": 7.20, "kritik_ust": 7.55, "birim": ""},
    "PCO2": {"min": 41.0, "max": 51.0, "kritik_alt": 25.0, "kritik_ust": 65.0, "birim": "mmHg"},
    "cHCO3": {"min": 22.0, "max": 28.0, "kritik_alt": 15.0, "kritik_ust": 35.0, "birim": "mmol/L"},
    "BE": {"min": -2.0, "max": 3.0, "kritik_alt": -10.0, "kritik_ust": 10.0, "birim": "mmol/L"},
    "K": {"min": 3.5, "max": 4.5, "kritik_alt": 3.0, "kritik_ust": 5.5, "birim": "mmol/L"},
    "Na": {"min": 135.0, "max": 148.0, "kritik_alt": 125.0, "kritik_ust": 155.0, "birim": "mmol/L"},
    "Ca_ionize": {"min": 1.11, "max": 1.35, "kritik_alt": 0.90, "kritik_ust": 1.50, "birim": "mmol/L"},
    "Cl": {"min": 98.0, "max": 107.0, "kritik_alt": 85.0, "kritik_ust": 115.0, "birim": "mmol/L"},
    "AG": {"min": 10.0, "max": 14.0, "kritik_alt": None, "kritik_ust": 18.0, "birim": "mmol/L"},
    "Laktat": {"min": 0.5, "max": 2.2, "kritik_alt": None, "kritik_ust": 4.0, "birim": "mmol/L"},
    "Glukoz": {"min": 74.0, "max": 106.0, "kritik_alt": 55.0, "kritik_ust": 250.0, "birim": "mg/dL"},
    "Hb": {"min": 11.5, "max": 17.4, "kritik_alt": 7.5, "kritik_ust": 19.0, "birim": "g/dL"},
    "Hct": {"min": 35.0, "max": 50.0, "kritik_alt": 22.0, "kritik_ust": 58.0, "birim": "%"},
    "Osmolalite": {"min": 271.0, "max": 303.0, "kritik_alt": 250.0, "kritik_ust": 320.0, "birim": "mOsm/kg"}
}

def veri_ayikla(ham_metin):
    bulunanlar = {}
    kaliplar = {
        "pH": r"\bpH\s*[:\-]?\s*(\d[\.,]\d{2,3})",
        "PCO2": r"\bPCO2\s*[:\-]?\s*(\d{2,3}[\.,]\d)",
        "cHCO3": r"\bc?HCO3\s*[:\-]?\s*(\d{1,2}[\.,]\d)",
        "BE": r"\bBE\s*[:\-]?\s*([\-+]?\d{1,2}(?:[\.,]\d)?)\s*mmol",
        "K": r"\bK\s*\(Potasyum\)\s*[:\-]?\s*(\d[\.,]\d)|\bK\s*[:\-]?\s*(\d[\.,]\d)\s*mmol",
        "Na": r"\bNa\s*\(Sodyum\)\s*[:\-]?\s*(\d{3})|\bNa\s*[:\-]?\s*(\d{3})\s*mmol",
        "Ca_ionize": r"\bCa\s*\(Kalsiyum\),\s*iyonize\s*[:\-]?\s*(\d[\.,]\d{2})|\bcCa2?\+?\s*[:\-]?\s*(\d[\.,]\d{2})",
        "Cl": r"\bCl\s*\(Klorür\)\s*[:\-]?\s*(\d{2,3})|\bCl\s*[:\-]?\s*(\d{2,3})\s*mmol",
        "AG": r"\bAG\s*[:\-]?\s*(\d{1,2}[\.,]\d)",
        "Laktat": r"\bLaktat\s*[:\-]?\s*(\d{1,2}[\.,]\d)",
        "Glukoz": r"\bGlukoz\s*[:\-]?\s*(\d{2,3})",
        "Hb": r"\bHb,\s*total\s*[:\-]?\s*(\d{1,2}[\.,]\d)|\bc?tHb\s*[:\-]?\s*(\d{1,2}[\.,]\d)",
        "Hct": r"\bHct\s*\(c\)\s*[:\-]?\s*(\d{2}[\.,]\d)|\bHct\s*[:\-]?\s*(\d{2}[\.,]\d)",
        "Osmolalite": r"\bOsmolalite\s*[:\-]?\s*(\d{3}[\.,]\d)"
    }
    for param, pattern in kaliplar.items():
        eslesme = re.search(pattern, ham_metin, re.IGNORECASE)
        if eslesme:
            deger_str = next((g for g in eslesme.groups() if g is not None), None)
            if deger_str:
                bulunanlar[param] = float(deger_str.replace(",", "."))
    return bulunanlar

def analiz_et(veriler, profil):
    if not veriler:
        st.warning("⚠️ Metinden anlamlı kan gazı parametresi okunamadı. Fotoğraf net değilse değerleri 'Hızlı Manuel Giriş' sekmesinden girebilirsiniz.")
        return

    st.session_state["son_veriler"] = veriler

    acil_uyarilar = []
    dikkat_uyarilari = []
    aksiyonlar = []

    for param, deger in veriler.items():
        ref = REFERANSLAR.get(param)
        if not ref:
            continue
        if ref["kritik_alt"] is not None and deger <= ref["kritik_alt"]:
            acil_uyarilar.append(f"**{param}: {deger} {ref['birim']}** (Kritik Düşük <= {ref['kritik_alt']})")
        elif ref["kritik_ust"] is not None and deger >= ref["kritik_ust"]:
            acil_uyarilar.append(f"**{param}: {deger} {ref['birim']}** (Kritik Yüksek >= {ref['kritik_ust']})")
        elif deger < ref["min"]:
            dikkat_uyarilari.append(f"**{param}: {deger} {ref['birim']}** (Düşük | Ref: {ref['min']}-{ref['max']})")
        elif deger > ref["max"]:
            dikkat_uyarilari.append(f"**{param}: {deger} {ref['birim']}** (Yüksek | Ref: {ref['min']}-{ref['max']})")

    pH = veriler.get("pH")
    pco2 = veriler.get("PCO2")
    hco3 = veriler.get("cHCO3")
    asit_baz_ozet = "Değerlendirme için pH, PCO2 ve HCO3 bekleniyor."

    if pH and pco2 and hco3:
        if pH < 7.31:
            if hco3 < 22:
                beklenen_arter = (1.5 * hco3) + 8
                alt, ust = beklenen_arter + 2, beklenen_arter + 8
                asit_baz_ozet = f"**METABOLİK ASİDOZ** (pH: {pH}, HCO3: {hco3}) | Beklenen Venöz PCO2: {alt:.1f}-{ust:.1f} mmHg"
                if pco2 > ust:
                    acil_uyarilar.append("**Eşlik eden SOLUNUMSAL ASİDOZ** (Yetersiz solunum kompanzasyonu!)")
                if pH < 7.20 or hco3 < 15:
                    aksiyonlar.append("**Derin Metabolik Asidoz:** IV Sodyum Bikarbonat replasmanı veya acil diyaliz endikasyonunu değerlendir. *(Aşağıdaki Doz Hesaplayıcıyı kullanabilirsiniz)*")
                else:
                    aksiyonlar.append("**Hafif/Orta Metabolik Asidoz:** Oral Sodyum Bikarbonat (Bikarbonat kapsül/toz) başlanmasını değerlendir.")
            elif pco2 > 51:
                asit_baz_ozet = f"**SOLUNUMSAL ASİDOZ** (pH: {pH}, PCO2: {pco2})"
                aksiyonlar.append("**Solunumsal Asidoz:** Hipervolemi (akciğer ödemi), solunum depresyonu veya KOAH açısından fizik muayene ve akciğer grafisi değerlendir.")
        elif pH > 7.41:
            if hco3 > 28:
                asit_baz_ozet = f"**METABOLİK ALKALOZ** (pH: {pH}, HCO3: {hco3})"
                aksiyonlar.append("**Metabolik Alkaloz:** Diüretik (Furosemid) fazlalığı, volüm kontraksiyonu veya kusma/NG drenajı sorgula.")
            elif pco2 < 41:
                asit_baz_ozet = f"**SOLUNUMSAL ALKALOZ** (pH: {pH}, PCO2: {pco2})"
        else:
            asit_baz_ozet = f"**Normal / Kompanse Asit-Baz Dengesi** (pH: {pH}, PCO2: {pco2}, HCO3: {hco3})"

    k = veriler.get("K")
    if k is not None:
        if k < 3.5:
            aksiyonlar.append(f"**Hipokalemi (K: {k}):** 12 derivasyonlu EKG çek. Diüretik tedavisini gözden geçir. KBY/Nakil hastasına uygun hızda Oral veya IV Potasyum replasmanı planla. *(Aşağıdaki Doz Hesaplayıcıya aktarıldı)*")
        elif k > 5.0:
            aksiyonlar.append(f"**Hiperkalemi (K: {k}):** Acil EKG çek. {'Kalsinörin inhibitörü (Takrolimus/Siklosporin) veya ACEi/ARB kaynaklı Tip 4 RTA açısından ilaç düzeylerini kontrol et. ' if 'Nakil' in profil else ''}K >= 5.5 ise Kalsiyum Glukonat, İnsülin-Dekstroz, Salbutamol, Potasyum bağlayıcı veya Diyaliz değerlendir.")

    ag = veriler.get("AG")
    laktat = veriler.get("Laktat")
    if ag is not None and ag > 14:
        if laktat and laktat <= 2.2:
            aksiyonlar.append(f"**Yüksek Anyon Açığı (AG: {ag}) + Normal Laktat:** Üremik asit/fosfat birikimi veya ketoasidoz açısından üre, kreatinin, fosfor ve kan ketonu kontrol et.")
        elif laktat and laktat > 2.2:
            acil_uyarilar.append(f"**LAKTİK ASİDOZ RİSKİ (AG: {ag}, Laktat: {laktat}):** Sepsis, greft/doku hipoperfüzyonu veya hipovolemi açısından acil değerlendir!")

    ca = veriler.get("Ca_ionize")
    if ca is not None and ca < 1.11:
        aksiyonlar.append(f"**Hipokalsemi (İyonize Ca: {ca}):** Kalsiyum ve aktif D vitamini (Kalsitriol) tedavisini düzenle; Chvostek/Trousseau ve kramp sorgula.")

    hb = veriler.get("Hb")
    if hb is not None and hb < 10.0:
        aksiyonlar.append(f"**Anemi (Hb: {hb}):** {'Post-op/cerrahi kanama, hemoliz veya EPO/demir eksikliği açısından tam kan ve retikülosit kontrol et.' if 'Nakil' in profil else 'Demir depoları (Ferritin, TSAT) ve EPO ihtiyacını değerlendir.'}")

    st.divider()
    if acil_uyarilar:
        st.error("🚨 **ACİL / KRİTİK UYARILAR**")
        for u in acil_uyarilar:
            st.markdown(f"- {u}")

    st.info(f"🧪 **Asit-Baz Özeti:** {asit_baz_ozet}")

    if aksiyonlar:
        st.success("📋 **ÖNERİLEN KLİNİK AKSİYONLAR**")
        for i, a in enumerate(aksiyonlar, 1):
            st.markdown(f"{i}. {a}")
    elif not acil_uyarilar:
        st.success("✅ Acil müdahale gerektiren kritik bir elektrolit veya asit-baz bozukluğu saptanmadı.")

    if dikkat_uyarilari:
        with st.expander("⚠️ Referans Dışı Diğer Parametreler", expanded=True):
            for d in dikkat_uyarilari:
                st.markdown(f"- {d}")

    with st.expander("📊 Okunan Tüm Parametreler Tablosu"):
        st.json(veriler)

# --- ANA ARAYÜZ ---
st.title("🩺 Venöz Kan Gazı Asistanı")
profil = st.selectbox("Hasta Profili Seçin:", ["KBY / Pre-op Hazırlık", "Böbrek Nakli Sonrası (Post-op)", "Genel Hasta"])

tab1, tab2, tab3 = st.tabs(["📷 Kamera / Fotoğraf", "📋 Metin Yapıştır", "⌨️ Hızlı Manuel Giriş"])

with tab1:
    st.caption("Kan gazı çıktısının veya monitörün fotoğrafını çekin ya da galeriden seçin.")
    kamera_foto = st.camera_input("Fotoğraf Çek")
    galeri_foto = st.file_uploader("Veya Galeriden Yükle", type=["jpg", "jpeg", "png"])
    
    aktif_gorsel = kamera_foto if kamera_foto else galeri_foto
    if aktif_gorsel:
        image = Image.open(aktif_gorsel)
        with st.spinner("Fotoğraf okunuyor ve analiz ediliyor..."):
            img_np = np.array(image)
            sonuclar = reader.readtext(img_np, detail=0)
            okunan_metin = " ".join(sonuclar)
            veriler = veri_ayikla(okunan_metin)
            analiz_et(veriler, profil)

with tab2:
    ham_metin = st.text_area("HBYS'den kopyaladığınız kan gazı sonucunu buraya yapıştırın:", height=150)
    if st.button("Metni Analiz Et", type="primary", use_container_width=True):
        veriler = veri_ayikla(ham_metin)
        analiz_et(veriler, profil)

with tab3:
    st.caption("OCR'ın okuyamadığı durumlarda veya hızlı yatakbaşı girişi için:")
    col1, col2 = st.columns(2)
    with col1:
        m_ph = st.number_input("pH", value=7.38, step=0.01, format="%.3f")
        m_pco2 = st.number_input("PCO2 (mmHg)", value=42.0, step=0.5)
        m_hco3 = st.number_input("cHCO3 (mmol/L)", value=24.0, step=0.5)
        m_k = st.number_input("Potasyum - K (mmol/L)", value=4.0, step=0.1)
    with col2:
        m_na = st.number_input("Sodyum - Na (mmol/L)", value=138.0, step=1.0)
        m_ca = st.number_input("İyonize Ca (mmol/L)", value=1.15, step=0.02)
        m_laktat = st.number_input("Laktat (mmol/L)", value=1.2, step=0.1)
        m_hb = st.number_input("Hemoglobin (g/dL)", value=11.5, step=0.1)
    if st.button("Manuel Değerleri Analiz Et", use_container_width=True):
        manuel_veriler = {
            "pH": m_ph, "PCO2": m_pco2, "cHCO3": m_hco3, "K": m_k,
            "Na": m_na, "Ca_ionize": m_ca, "Laktat": m_laktat, "Hb": m_hb
        }
        analiz_et(manuel_veriler, profil)

# =====================================================================
# REPLASMAN DOZ HESAPLAYICI MODÜLÜ (KCl ve NaHCO3)
# =====================================================================
st.divider()
st.subheader("💉 Replasman Doz Hesaplayıcı (KCl & NaHCO3)")
st.caption("Standart Türkiye hastane formlarına göre hesaplanır (1 Ampul %7,5 KCl = 10 mEq | 1 Ampul %8,4 NaHCO3 = 10 mEq).")

kilo = st.number_input("Hastanın Kilosu (kg):", min_value=20.0, max_value=250.0, value=70.0, step=1.0)

calc_tab1, calc_tab2 = st.tabs(["⚡ Potasyum (KCl) Hesaplayıcı", "🧪 Bikarbonat (NaHCO3) Hesaplayıcı"])

# --- 1. POTASYUM HESAPLAYICI ---
with calc_tab1:
    varsayilan_k = float(st.session_state["son_veriler"].get("K", 2.9))
    if varsayilan_k > 6.0:
        varsayilan_k = 2.9

    c1, c2 = st.columns(2)
    with c1:
        mevcut_k = st.number_input("Mevcut K (mmol/L):", min_value=1.0, max_value=6.0, value=varsayilan_k, step=0.1)
    with c2:
        hedef_k = st.number_input("Hedef K (mmol/L):", min_value=3.5, max_value=4.5, value=4.0, step=0.1)

    damar_yolu = st.radio("Uygulama Yolu:", ["Periferik Damar Yolu", "Santral Venöz Kateter (SVK)"], horizontal=True)

    if mevcut_k >= hedef_k:
        st.success(f"Mevcut potasyum ({mevcut_k} mmol/L) hedef değerin altında değil. Replasman gerekmiyor.")
    else:
        # Klinik kural: Serum K'daki her 0.3 mmol/L düşüş yaklaşık 100 mEq total vücut açığına karşılık gelir.
        # Ancak KBY/Nakil hastalarında böbrekten atılım kısıtlı olabileceği için temkinli replasman esastır.
        fark_k = hedef_k - mevcut_k
        tahmini_acik_meq = (fark_k / 0.3) * 100
        
        # KBY hastalarında tek seferde/ilk 24 saatte verilecek güvenli replasman dozu
        if "KBY" in profil:
            onerilen_baslangic_meq = min(tahmini_acik_meq * 0.5, 40.0 if mevcut_k >= 3.0 else 60.0)
        else:
            onerilen_baslangic_meq = min(tahmini_acik_meq * 0.6, 80.0)

        ampul_kcl = round(onerilen_baslangic_meq / 10.0, 1)

        st.markdown(f"""
        * **Tahmini Total Vücut K Açığı:** ~{tahmini_acik_meq:.0f} mEq
        * **İlk Etapta Önerilen Güvenli Başlangıç Dozu:** **{onerilen_baslangic_meq:.0f} mEq** (**{ampul_kcl} Ampul** %7,5 KCl)
        """)

        if damar_yolu == "Periferik Damar Yolu":
            st.warning("""
            **Periferik İnfüzyon Kuralları:**
            * Maksimum hız: **10 mEq/saat** (1 Ampul/saat)
            * Maksimum konsantrasyon: **40 mEq/L** (Örn: 1000 mL %0,9 NaCl içine en fazla 4 ampul KCl; flebit riskini önlemek için)
            * *Not: Dekstrozlu sıvılar insülin salınımını uyararak potasyumu hücre içine sokup serum K'yı daha da düşürebilir; mümkünse %0,9 NaCl tercih edin.*
            """)
        else:
            st.warning("""
            **Santral Kateter (SVK) İnfüzyon Kuralları:**
            * Standart hız: **10–20 mEq/saat** (EKG monitörizasyonu altında)
            * Her **20–40 mEq** replasman sonrası kontrol kan gazı/elektrolit görülerek doza devam edilmelidir.
            """)

        if "KBY" in profil:
            st.error("⚠️ **KBY Uyarısı:** Böbrek potasyum atılımı kısıtlı olduğu için 'rebound hiperkalemi' riski yüksektir. Dozun tamamını tek seferde yüklemeyin; ilk 2-3 ampul sonrası kontrol K görün.")

# --- 2. BİKARBONAT HESAPLAYICI ---
with calc_tab2:
    varsayilan_hco3 = float(st.session_state["son_veriler"].get("cHCO3", 16.0))
    if varsayilan_hco3 > 30.0:
        varsayilan_hco3 = 16.0

    b1, b2 = st.columns(2)
    with b1:
        mevcut_hco3 = st.number_input("Mevcut cHCO3 (mmol/L):", min_value=3.0, max_value=30.0, value=varsayilan_hco3, step=0.5)
    with b2:
        hedef_hco3 = st.number_input("Hedef cHCO3 (mmol/L):", min_value=18.0, max_value=24.0, value=20.0, step=0.5)

    if mevcut_hco3 >= hedef_hco3:
        st.success(f"Mevcut bikarbonat ({mevcut_hco3} mmol/L) hedef değerin altında değil. IV replasman gerekmiyor.")
    else:
        # Bikarbonat Açığı Formülü = 0.5 * Kilo * (Hedef HCO3 - Mevcut HCO3)
        tam_acik_meq = 0.5 * kilo * (hedef_hco3 - mevcut_hco3)
        ilk_24_saat_meq = tam_acik_meq * 0.5
        
        tam_ampul = round(tam_acik_meq / 10.0, 1)
        onerilen_ampul = round(ilk_24_saat_meq / 10.0, 1)

        st.markdown(f"""
        * **Hesaplanan Total Bikarbonat Açığı:** {tam_acik_meq:.0f} mEq ({tam_ampul} Ampul %8,4 NaHCO3)
        * **İlk 24 Saatte Verilmesi Önerilen (%50 Defisit):** **{ilk_24_saat_meq:.0f} mEq** (**{onerilen_ampul} Ampul** %8,4 NaHCO3)
        """)

        st.info(f"""
        **Uygulama Şekli Önerisi:**
        * Hesaplanan **{onerilen_ampul:.0f} ampul** (%8,4 NaHCO3) genellikle **%5 Dekstroz** (veya hipotonik sıvı; hipernatremi yapmamak için) içine eklenerek **4–8 saatlik** yavaş infüzyon şeklinde verilir.
        * *Not: Her 10 mEq NaHCO3 ampulü beraberinde **10 mEq Sodyum (Na)** yükü getirir. Anürik/oligürik KBY hastasında akciğer ödemi ve hipernatremi açısından volüm durumunu kontrol edin.*
        """)

        if st.session_state["son_veriler"].get("Ca_ionize", 1.15) < 1.11:
            st.error("🚨 **Hipokalsemi Uyarısı:** Hastada mevcut hipokalsemi var! Bikarbonat infüzyonu kan pH'ını yükselterek iyonize kalsiyumu daha da düşürebilir ve tetani/nöbet tetikleyebilir. Önce kalsiyumu destekleyin.")
