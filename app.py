"""
ATS CV Optimizer - Streamlit Web Application
Groq AI destekli, kullanici API key girmez.
CV analizi + AI feedback botu.
"""

import streamlit as st
import re
import io
from collections import Counter
from groq import Groq

try:
    import pdfplumber
    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

try:
    from docx import Document
    DOCX_SUPPORT = True
except ImportError:
    DOCX_SUPPORT = False


def get_groq_client():
    """Groq client'i Streamlit secrets'tan al."""
    api_key = st.secrets["GROQ_API_KEY"]
    return Groq(api_key=api_key)


def parse_pdf(file_bytes):
    if not PDF_SUPPORT:
        st.error("pdfplumber yuklu degil.")
        return ""
    text_parts = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


def parse_docx(file_bytes):
    if not DOCX_SUPPORT:
        st.error("python-docx yuklu degil.")
        return ""
    doc = Document(io.BytesIO(file_bytes))
    return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])


def extract_text_from_upload(uploaded_file):
    file_bytes = uploaded_file.read()
    name = uploaded_file.name.lower()
    if name.endswith(".pdf"):
        return parse_pdf(file_bytes)
    elif name.endswith(".docx"):
        return parse_docx(file_bytes)
    else:
        st.error("Desteklenmeyen dosya turu.")
        return ""


def temizle(text):
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    return text


# ── ESANLAMLI KELIME SOZLUGU (Turkce/Ingilizce capraz eslesme) ──
ESANLAMLILAR = {
    # Satis / Sales
    "satis": ["sales", "selling", "musteri temsilcisi", "saha satis", "pazarlama", "magaza"],
    "sales": ["satis", "musteri temsilcisi", "saha satis", "pazarlama", "selling"],
    # Yonetim / Management
    "yonetim": ["management", "liderlik", "supervisor", "team lead", "takim lideri", "koordinasyon"],
    "management": ["yonetim", "liderlik", "koordinasyon", "takim lideri"],
    "leadership": ["liderlik", "yonetim", "takim lideri", "koordinasyon"],
    # Iletisim / Communication
    "iletisim": ["communication", "diksiyon", "sunum", "presentation", "gorusme"],
    "communication": ["iletisim", "diksiyon", "sunum", "gorusme"],
    # Musteri / Customer
    "musteri": ["customer", "client", "memnuniyet", "satisfaction", "iliskiler"],
    "customer": ["musteri", "client", "memnuniyet", "iliskiler"],
    # Ekip / Team
    "ekip": ["team", "takim", "group", "calisma grubu"],
    "team": ["ekip", "takim", "grup"],
    # Deneyim / Experience
    "deneyim": ["experience", "tecrube", "gecmis", "background"],
    "experience": ["deneyim", "tecrube", "gecmis"],
    # Ehliyet / License
    "ehliyet": ["license", "surucubelgesi", "b sinifi", "arac kullanimi", "driving"],
    "driving": ["ehliyet", "surucubelgesi", "b sinifi"],
    # Bilgisayar / Computer
    "bilgisayar": ["computer", "ms office", "excel", "word", "yazilim", "software"],
    "computer": ["bilgisayar", "ms office", "yazilim"],
    # Egitim / Education
    "egitim": ["education", "training", "lisans", "mezuniyet", "okul"],
    "education": ["egitim", "lisans", "mezuniyet", "okul"],
    # Sorumluluk / Responsibility
    "sorumluluk": ["responsibility", "gorev", "yukumluluk", "accountability"],
    "responsibility": ["sorumluluk", "gorev", "yukumluluk"],
    # Hedef / Target
    "hedef": ["target", "goal", "kpi", "performans", "basari"],
    "target": ["hedef", "goal", "kpi", "performans"],
    # Insan iliskileri
    "insan": ["people", "interpersonal", "iletisim", "iliskiler"],
    "interpersonal": ["insan iliskileri", "iletisim", "sosyal"],
    # Askerlik
    "askerlik": ["military", "tecilli", "muaf", "tamamlandi"],
    # Ikna
    "ikna": ["persuasion", "negotiation", "musteri kazanma", "pazarlama"],
}

# ── SEKTORE OZEL KEYWORD LISTESI ──
SEKTOR_KEYWORDLERI = {
    "satis": ["satis hedefi", "musteri portfoyu", "kota", "pipeline", "crm", "teklif", "sozlesme",
              "b2b", "b2c", "saha ziyareti", "demo", "pitch", "komisyon"],
    "it": ["python", "java", "sql", "api", "cloud", "aws", "docker", "git", "agile", "scrum",
           "javascript", "react", "backend", "frontend", "database"],
    "finans": ["muhasebe", "butce", "mali", "vergi", "bilanço", "excel", "erp", "sap", "fatura"],
    "insan_kaynaklari": ["ik", "isveren", "isveren markasi", "isseveran", "bordro", "performans",
                         "oryantasyon", "sgk", "is hukuku"],
    "pazarlama": ["sosyal medya", "seo", "dijital", "kampanya", "marka", "analitik", "google ads",
                  "instagram", "linkedin", "icerik"],
}


def sektor_tespit(jd_text):
    """Is ilanindaki sektoru tespit et."""
    text = jd_text.lower()
    skor = {}
    for sektor, kelimeler in SEKTOR_KEYWORDLERI.items():
        skor[sektor] = sum(1 for k in kelimeler if k in text)
    en_iyi = max(skor, key=skor.get)
    return en_iyi if skor[en_iyi] > 0 else None


def esanlamli_genislet(kelimeler_seti):
    """Verilen kelime setini esanlamlilariyla genislet."""
    genisletilmis = set(kelimeler_seti)
    for kelime in list(kelimeler_seti):
        if kelime in ESANLAMLILAR:
            genisletilmis.update(ESANLAMLILAR[kelime])
    return genisletilmis


def bigram_cikar(text):
    """Metinden iki kelimelik ifadeler cikar."""
    kelimeler = temizle(text).split()
    bigramlar = []
    for i in range(len(kelimeler) - 1):
        bigram = f"{kelimeler[i]} {kelimeler[i+1]}"
        if len(bigram) > 6:
            bigramlar.append(bigram)
    return bigramlar


def kelimeleri_cikar(text):
    stopwords = {
        've', 'veya', 'ile', 'bir', 'bu', 'da', 'de', 'icin', 'olan',
        'the', 'and', 'or', 'is', 'in', 'at', 'of', 'to', 'a', 'an',
        'for', 'on', 'with', 'as', 'by', 'be', 'are', 'was', 'were',
        'that', 'this', 'it', 'we', 'you', 'he', 'she', 'they', 'have',
        'has', 'had', 'will', 'would', 'can', 'could', 'should', 'may',
        'might', 'must', 'shall', 'do', 'does', 'did', 'not', 'but',
        'if', 'then', 'than', 'so', 'from', 'up', 'about', 'into',
        'olan', 'icin', 'veya', 'ile', 'her', 'daha', 'cok', 'gibi',
        'olan', 'olarak', 'olan', 'olmak', 'sahip', 'aranan'
    }
    kelimeler = temizle(text).split()
    return [k for k in kelimeler if len(k) > 2 and k not in stopwords]


def bolum_tespit(cv_text):
    text_lower = cv_text.lower()
    return {
        "experience": any(k in text_lower for k in [
            "experience", "deneyim", "is deneyimi", "work experience",
            "employment", "calistim", "is gecmisi", "kariyer"
        ]),
        "education": any(k in text_lower for k in [
            "education", "egitim", "university", "universite", "mezun",
            "degree", "lisans", "lise", "yuksek okul", "mba", "onlisans"
        ]),
        "skills": any(k in text_lower for k in [
            "skills", "yetenekler", "beceriler", "yetkinlikler",
            "competencies", "technical", "bilgi", "uzmanlik"
        ]),
        "certifications": any(k in text_lower for k in [
            "certification", "sertifika", "certificate", "license",
            "belge", "kurs", "egitim sertifikasi"
        ])
    }


def format_sorunlari_tespit(cv_text):
    sorunlar = []
    satirlar = cv_text.split('\n')

    # Tablo/sutun kontrolu
    kisa_satirlar = [s for s in satirlar if 0 < len(s.strip()) < 15]
    if len(kisa_satirlar) > 10:
        sorunlar.append("CV'niz tablo veya sutun formati iceriyor. ATS sistemleri tablolari okuyamaz.")

    # Uzun paragraf kontrolu
    uzun_satirlar = [s for s in satirlar if len(s.strip()) > 300]
    if uzun_satirlar:
        sorunlar.append("Cok uzun paragraflar var. Bullet point kullanmaniz onerilir.")

    # Bolum kontrolu
    bolumler = bolum_tespit(cv_text)
    if not bolumler["skills"]:
        sorunlar.append("'Skills/Beceriler' bolumu bulunamadi. ATS sistemleri bu bolumu arar.")
    if not bolumler["experience"]:
        sorunlar.append("'Experience/Deneyim' bolumu bulunamadi.")

    # Email kontrolu
    if not re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', cv_text):
        sorunlar.append("CV'de email adresi bulunamadi.")

    # Telefon kontrolu
    if not re.search(r'[\+]?[\d\s\-\(\)]{10,}', cv_text):
        sorunlar.append("CV'de telefon numarasi bulunamadi.")

    # Tarih formati kontrolu
    if not re.search(r'\b(20\d\d|19\d\d)\b', cv_text):
        sorunlar.append("CV'de yil/tarih bilgisi bulunamadi. Is deneyimlerinize tarih ekleyin.")

    # Ozel karakter kontrolu
    if any(c in cv_text for c in ['★', '●', '◆', '▸', '✦', '☎', '✉']):
        sorunlar.append("Ozel karakterler (★, ●, ◆ vb.) ATS sistemlerinde hatali okunabilir.")

    return sorunlar


def keyword_analizi(cv_text, jd_text):
    """Gelismis keyword analizi: esanlamlilar + bigram + sektor destegi."""

    # Tekil kelimeler
    cv_kelimeler = set(kelimeleri_cikar(cv_text))
    jd_kelimeler = kelimeleri_cikar(jd_text)

    # Bigramlar
    cv_bigramlar = set(bigram_cikar(cv_text))
    jd_bigramlar = set(bigram_cikar(jd_text))

    # JD'deki onemli kelimeler
    jd_sayac = Counter(jd_kelimeler)
    onemli_jd = {k for k, v in jd_sayac.items() if len(k) > 3}

    # CV'yi esanlamlilariyla genislet
    cv_genisletilmis = esanlamli_genislet(cv_kelimeler)

    # Sektore ozel kontrol
    sektor = sektor_tespit(jd_text)
    sektor_eksik = []
    if sektor and sektor in SEKTOR_KEYWORDLERI:
        sektor_kelimeleri = SEKTOR_KEYWORDLERI[sektor]
        sektor_eksik = [k for k in sektor_kelimeleri if k not in cv_text.lower()][:5]

    # Eslesen ve eksik kelimeler
    eslesen = onemli_jd & cv_genisletilmis
    eksik = onemli_jd - cv_genisletilmis

    # Bigram eslesmesi
    bigram_eslesen = onemli_jd & {b.split()[0] for b in cv_bigramlar}
    eslesen = eslesen | bigram_eslesen

    # Genel kelimeleri filtrele
    genel = {
        'must', 'will', 'work', 'good', 'well', 'able', 'also', 'more',
        'than', 'our', 'your', 'their', 'have', 'been', 'they', 'from',
        'such', 'both', 'each', 'need', 'new', 'high', 'other', 'some',
        'what', 'when', 'where', 'which', 'while', 'how', 'all', 'any',
        'olan', 'icin', 'veya', 'ile', 'olarak', 'sahip', 'aranan', 'olan'
    }
    eksik = {k for k in eksik if k not in genel and len(k) > 3}

    # Sektor eksiklerini de ekle
    tum_eksik = list(eksik)[:10] + sektor_eksik[:5]

    return list(eslesen), tum_eksik[:15]


def puan_hesapla(cv_text, jd_text, bolumler, eslesen, format_sorunlari):
    """Gelismis puan hesaplama."""
    puan = 0
    breakdown = {}

    # 1. Keyword eslesmesi (30 puan) - esanlamlilarla genisletilmis
    cv_genisletilmis = esanlamli_genislet(set(kelimeleri_cikar(cv_text)))
    jd_kelimeler = set(kelimeleri_cikar(jd_text))
    gercek_eslesen = cv_genisletilmis & jd_kelimeler
    kw_oran = len(gercek_eslesen) / max(len(jd_kelimeler), 1)
    kw_puan = min(30, int(kw_oran * 100))
    breakdown["keyword_match"] = kw_puan
    puan += kw_puan

    # 2. Bolum yapisi (20 puan)
    bolum_puan = sum(5 for v in bolumler.values() if v)
    breakdown["section_structure"] = bolum_puan
    puan += bolum_puan

    # 3. Bullet kalitesi (20 puan)
    bullet_sayisi = len(re.findall(r'(?m)^[\s]*[-*•]', cv_text))
    guclu_fiil = len(re.findall(
        r'\b(led|managed|developed|created|achieved|improved|implemented|designed|'
        r'yonettim|gelistirdim|olusturdum|artirdim|sagladim|koordine|tasarladim)\b',
        cv_text.lower()
    ))
    bullet_puan = min(20, bullet_sayisi * 2 + guclu_fiil)
    breakdown["bullet_quality"] = bullet_puan
    puan += bullet_puan

    # 4. Format (15 puan)
    format_puan = max(0, 15 - len(format_sorunlari) * 3)
    breakdown["formatting"] = format_puan
    puan += format_puan

    # 5. Sayisal basarilar (15 puan)
    sayisal = re.findall(
        r'\d+\s*(%|yil|ay|kisi|milyon|bin|proje|musteri|year|month|people|million|k\b|'
        r'satis|gelir|buyume|artis|azalis)',
        cv_text.lower()
    )
    sayisal_puan = min(15, len(sayisal) * 3)
    breakdown["quantified_achievements"] = sayisal_puan
    puan += sayisal_puan

    return min(100, puan), breakdown


def ai_feedback_olustur(cv_text, jd_text, puan, eksik, format_sorunlari, tr=True):
    """AI ile cok detayli ve CV'ye ozel feedback olustur."""
    client = get_groq_client()
    
    prompt = f"""Sen Turkiye'nin en deneyimli kariyer kocu ve CV uzmanisın. 15 yildir Fortune 500 sirketlerinde ise alim yaptin ve binlerce kisinin CV'sini degerlendirdin.

Asagidaki CV'yi ve is ilanini CIDDEN dikkatlice oku. Yuzeysel, genel laflar etme. CV'deki GERCEK bilgilere dayanarak, o kişiye OZEL, somut ve donusturucu geri bildirim ver.

═══════════════════════════════
CV:
{cv_text[:3000]}

═══════════════════════════════
IS ILANI:
{jd_text[:2000]}

═══════════════════════════════
ATS PUANI: {puan}/100
EKSIK KELIMELER: {', '.join(eksik[:10]) if eksik else 'Hic eksik yok'}
FORMAT SORUNLARI: {', '.join(format_sorunlari[:3]) if format_sorunlari else 'Hic sorun yok'}

═══════════════════════════════

Asagidaki formatta TURKCE yaz. Her bolumu eksiksiz doldur. GERCEKTEN CV'yi oku ve o kisiye ozel yaz:

## 👤 Sana Ozel Degerlendirme
[CV'deki GERCEK bilgilere gore (isim, deneyim, egitim, beceriler varsa bunlara degin) kisisel bir giris yaz. "CV'nizi inceledim" gibi genel laflar ETME, direkt o kisinin bilgilerine gonder.]

## ✅ Guclu Yonlerin
[CV'de GERCEKTEN iyi olan 3-4 seyi yaz. Genel ovgu degil, spesifik: "X yillik deneyimin bu pozisyon icin cok degerli cunku..." gibi]

## ⚠️ Mutlaka Duzeltmen Gerekenler
[En az 4-5 somut, spesifik eksik veya hata. Her biri icin: Ne eksik → Neden onemli → Nasil duzelteceksin (ornek ver)]

## 🎯 Bu Is Icin Sana Ozel Tavsiyeler  
[Is ilanindaki SPESIFIK gereksinimlere gore, o kisinin CV'sindeki bilgilerle nasil one cikabilecegini anlat. Ornek: "Ilanda B ehliyeti isteniyor, bunu CV'nin en ustune ekle cunku..."]

## 💬 Mulakat Hazirlik
[Bu pozisyon icin sorulabilecek 3 spesifik soru ve nasil cevaplamasi gerektigine dair ipuclari. CV'deki bilgilere gore kisisellestir.]

## 🚀 Bir Sonraki Adimin
[Bu kisinin kariyer hedefleri acisindan 2-3 somut, uygulanabilir adim. Motivasyon ver ama gercekci ol.]

ONEMLI: Turkce yaz. Samimi, direkt ve motive edici ol. Genel laflardan kac, CV'deki GERCEK bilgilere dayanarak yaz."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=2000,
    )
    return response.choices[0].message.content


def ai_soru_cevap(soru, cv_text, jd_text, mesaj_gecmisi, tr=True):
    """Kullanicinin sorularini AI ile cevapla."""
    client = get_groq_client()
    
    sistem_mesaji = f"""Sen bir kariyer kocu ve CV uzmanisın. Kullanicinin CV'si ve basvurdugu is ilani hakkinda {"Turkce" if tr else "English"} olarak yardimci oluyorsun.

CV Ozeti:
{cv_text[:2000]}

Is Ilani Ozeti:
{jd_text[:1000]}

Her zaman Turkce cevap ver. Samimi, yardimci ve pratik tavsiyeler ver. Cover letter, mulakat hazirlik, maas musaveresi gibi konularda yardimci ol."""

    mesajlar = [{"role": "system", "content": sistem_mesaji}]
    mesajlar.extend(mesaj_gecmisi)
    mesajlar.append({"role": "user", "content": soru})

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=mesajlar,
        temperature=0.7,
        max_tokens=1000,
    )
    return response.choices[0].message.content


def score_color(score):
    if score >= 75:
        return "#2ecc71"
    elif score >= 50:
        return "#f39c12"
    else:
        return "#e74c3c"


def render_score_gauge(score):
    color = score_color(score)
    label = "Guclu Esleme ✅" if score >= 75 else ("Orta Esleme ⚠️" if score >= 50 else "Zayif Esleme ❌")
    filled = int(score / 5)
    bar = "█" * filled + "░" * (20 - filled)
    st.markdown(
        f"<h1 style='color:{color}; font-size:3rem;'>{score}/100</h1>"
        f"<p style='font-family:monospace; letter-spacing:2px; color:{color};'>{bar}</p>"
        f"<p style='font-size:1.2rem;'>{label}</p>",
        unsafe_allow_html=True
    )


def main():
    st.set_page_config(page_title="ATS CV Optimizer", page_icon="📄", layout="wide")

    if "analiz_yapildi" not in st.session_state:
        st.session_state.analiz_yapildi = False
    if "cv_text" not in st.session_state:
        st.session_state.cv_text = ""
    if "jd_text" not in st.session_state:
        st.session_state.jd_text = ""
    if "mesaj_gecmisi" not in st.session_state:
        st.session_state.mesaj_gecmisi = []
    if "sohbet_mesajlari" not in st.session_state:
        st.session_state.sohbet_mesajlari = []
    if "dil" not in st.session_state:
        st.session_state.dil = None

    # Dil secimi ekrani
    if st.session_state.dil is None:
        st.markdown("""
        <div style='text-align:center; padding: 80px 20px;'>
            <h1 style='font-size:3rem;'>📄 ATS CV Optimizer</h1>
            <p style='font-size:1.2rem; color:#666;'>AI destekli CV analizi ve kariyer kocu</p>
            <p style='font-size:1.2rem; color:#666;'>AI-powered CV analysis and career coach</p>
            <br>
        </div>
        """, unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("### 🌐 Dil Secin / Choose Language")
            lang_col1, lang_col2 = st.columns(2)
            with lang_col1:
                if st.button("🇹🇷  Turkce", use_container_width=True, type="primary"):
                    st.session_state.dil = "tr"
                    st.rerun()
            with lang_col2:
                if st.button("🇬🇧  English", use_container_width=True, type="primary"):
                    st.session_state.dil = "en"
                    st.rerun()
        return

    tr = st.session_state.dil == "tr"

    st.title("📄 ATS CV Optimizer")
    st.caption("AI destekli CV analizi ve kariyer kocu" if tr else "AI-powered CV analysis and career coach")

    with st.sidebar:
        if st.button("🌐 Dil Degistir / Change Language"):
            st.session_state.dil = None
            st.session_state.analiz_yapildi = False
            st.rerun()
        st.markdown("---")
        st.header("Nasil Calisir?" if tr else "How It Works")
        if tr:
            st.markdown("1. CV'nizi yapistirin\n2. Is ilanini yapistirin\n3. Analiz Et butonuna basin\n4. AI feedback alin\n5. AI bota soru sorun")
        else:
            st.markdown("1. Paste your CV\n2. Paste the Job Description\n3. Click Analyze\n4. Get AI feedback\n5. Chat with AI assistant")
        st.markdown("---")
        st.success("✅ Free / Ucretsiz\n\n✅ No API key\n\n✅ AI powered")

    st.divider()

    col_cv, col_jd = st.columns(2)

    with col_cv:
        st.subheader("📋 CV'niz" if tr else "📋 Your CV")
        input_options = ["Metin yapistir", "Dosya yukle (PDF / DOCX)"] if tr else ["Paste text", "Upload file (PDF / DOCX)"]
        input_method = st.radio("Giris yontemi" if tr else "Input method", input_options, horizontal=True)
        cv_text = ""
        if input_method in ["Metin yapistir", "Paste text"]:
            cv_text = st.text_area(
                "CV'nizi buraya yapistirin" if tr else "Paste your CV here",
                height=300,
                placeholder="Ad Soyad\nemail@gmail.com\n\nDENEYIM\n..." if tr else "John Doe\njohn@email.com\n\nEXPERIENCE\n..."
            )
        else:
            uploaded = st.file_uploader("CV Yukle" if tr else "Upload CV", type=["pdf", "docx"], label_visibility="collapsed")
            if uploaded:
                with st.spinner("Dosya okunuyor..." if tr else "Reading file..."):
                    cv_text = extract_text_from_upload(uploaded)
                if cv_text:
                    st.success(f"{len(cv_text.split())} {'kelime okundu' if tr else 'words extracted'}.")

    with col_jd:
        st.subheader("🎯 Is Ilani" if tr else "🎯 Job Description")
        jd_text = st.text_area(
            "Is ilanini buraya yapistirin" if tr else "Paste the Job Description here",
            height=300,
            placeholder="Aradigimiz kisi en az 2 yil deneyimli..." if tr else "We are looking for a candidate with at least 2 years of experience..."
        )

    st.divider()
    analyze_btn = st.button(
        "🔍 CV'yi Analiz Et" if tr else "🔍 Analyze CV",
        type="primary",
        use_container_width=True
    )

    if analyze_btn:
        if not cv_text.strip():
            st.error("Lutfen CV'nizi girin." if tr else "Please provide your CV.")
            st.stop()
        if not jd_text.strip():
            st.error("Lutfen is ilanini girin." if tr else "Please paste the Job Description.")
            st.stop()

        st.session_state.cv_text = cv_text
        st.session_state.jd_text = jd_text
        st.session_state.mesaj_gecmisi = []
        st.session_state.sohbet_mesajlari = []

        with st.spinner("Analiz ediliyor..." if tr else "Analyzing..."):
            bolumler = bolum_tespit(cv_text)
            eslesen, eksik = keyword_analizi(cv_text, jd_text)
            format_sorunlari = format_sorunlari_tespit(cv_text)
            puan, breakdown = puan_hesapla(cv_text, jd_text, bolumler, eslesen, format_sorunlari)

        with st.spinner("AI feedback hazirlaniyor..." if tr else "Preparing AI feedback..."):
            try:
                ai_feedback = ai_feedback_olustur(cv_text, jd_text, puan, eksik, format_sorunlari, tr)
            except Exception as e:
                ai_feedback = "AI feedback su an hazirlanamadi." if tr else "AI feedback could not be generated."

        st.session_state.analiz_yapildi = True
        st.session_state.bolumler = bolumler
        st.session_state.eslesen = eslesen
        st.session_state.eksik = eksik
        st.session_state.format_sorunlari = format_sorunlari
        st.session_state.puan = puan
        st.session_state.breakdown = breakdown
        st.session_state.ai_feedback = ai_feedback

    if st.session_state.analiz_yapildi:
        puan = st.session_state.puan
        breakdown = st.session_state.breakdown
        bolumler = st.session_state.bolumler
        eslesen = st.session_state.eslesen
        eksik = st.session_state.eksik
        format_sorunlari = st.session_state.format_sorunlari
        ai_feedback = st.session_state.ai_feedback

        st.success("Analiz tamamlandi!" if tr else "Analysis complete!")
        st.divider()
        st.header("📊 ATS Analiz Raporu" if tr else "📊 ATS Analysis Report")

        r1, r2 = st.columns([1, 2])
        with r1:
            st.subheader("ATS Puani" if tr else "ATS Score")
            render_score_gauge(puan)

        with r2:
            st.subheader("Puan Dagilimi" if tr else "Score Breakdown")
            if tr:
                labels = {
                    "keyword_match": "Keyword Eslesmesi (30)",
                    "section_structure": "Bolum Yapisi (20)",
                    "bullet_quality": "Bullet Kalitesi (20)",
                    "formatting": "Format (15)",
                    "quantified_achievements": "Sayisal Basarilar (15)"
                }
            else:
                labels = {
                    "keyword_match": "Keyword Match (30)",
                    "section_structure": "Section Structure (20)",
                    "bullet_quality": "Bullet Quality (20)",
                    "formatting": "Formatting (15)",
                    "quantified_achievements": "Quantified Achievements (15)"
                }
            for key, label in labels.items():
                val = breakdown.get(key, 0)
                max_val = int(re.search(r"\((\d+)\)", label).group(1))
                pct = min(100, int((val / max_val) * 100)) if max_val else 0
                st.write(f"**{label}**: {val}/{max_val}")
                st.progress(pct)

        st.divider()

        st.subheader("🤖 AI Kariyer Kocu Feedback" if tr else "🤖 AI Career Coach Feedback")
        st.markdown(
            f"<div style='background:#f8f9ff; border-left:4px solid #4a90e2; padding:20px; border-radius:8px; line-height:1.8;'>{ai_feedback}</div>",
            unsafe_allow_html=True
        )

        st.divider()

        col_kw, col_fmt = st.columns(2)
        with col_kw:
            st.subheader("🔑 Eksik Kelimeler" if tr else "🔑 Missing Keywords")
            if eksik:
                tags_html = " ".join(
                    f"<span style='background:#fff3cd; border:1px solid #ffc107; border-radius:4px; padding:2px 8px; margin:2px; display:inline-block;'>🏷️ {kw}</span>"
                    for kw in eksik
                )
                st.markdown(tags_html, unsafe_allow_html=True)
            else:
                st.success("Kritik eksik kelime bulunamadi." if tr else "No critical missing keywords.")
            st.markdown("---")
            st.subheader("✅ Eslesen Kelimeler" if tr else "✅ Matched Keywords")
            if eslesen:
                tags_html = " ".join(
                    f"<span style='background:#d4edda; border:1px solid #28a745; border-radius:4px; padding:2px 8px; margin:2px; display:inline-block;'>✓ {kw}</span>"
                    for kw in eslesen[:20]
                )
                st.markdown(tags_html, unsafe_allow_html=True)

        with col_fmt:
            st.subheader("⚠️ Format Sorunlari" if tr else "⚠️ Formatting Issues")
            if format_sorunlari:
                for sorun in format_sorunlari:
                    st.warning(sorun)
            else:
                st.success("Buyuk format sorunu bulunamadi." if tr else "No major formatting issues.")

        st.divider()

        st.subheader("💬 AI Kariyer Asistani" if tr else "💬 AI Career Assistant")
        st.markdown(
            "CV'niz hakkinda soru sorun!" if tr else "Ask questions about your CV!"
        )

        hizli_col1, hizli_col2, hizli_col3 = st.columns(3)
        with hizli_col1:
            btn1 = "📝 Cover Letter Yaz" if tr else "📝 Write Cover Letter"
            if st.button(btn1, use_container_width=True):
                st.session_state.hizli_soru = "Bu is icin Turkce cover letter yazar misin?" if tr else "Can you write a cover letter for this job in English?"
        with hizli_col2:
            btn2 = "🎯 Mulakat Sorulari" if tr else "🎯 Interview Questions"
            if st.button(btn2, use_container_width=True):
                st.session_state.hizli_soru = "Bu is icin hangi mulakat sorulari gelebilir?" if tr else "What interview questions might come up for this job?"
        with hizli_col3:
            btn3 = "💰 Maas Tavsiyesi" if tr else "💰 Salary Advice"
            if st.button(btn3, use_container_width=True):
                st.session_state.hizli_soru = "Bu pozisyon icin ne kadar maas beklentisi olmali?" if tr else "What salary should I expect for this position?"

        for mesaj in st.session_state.sohbet_mesajlari:
            with st.chat_message(mesaj["role"]):
                st.markdown(mesaj["content"])

        if "hizli_soru" in st.session_state and st.session_state.hizli_soru:
            soru = st.session_state.hizli_soru
            st.session_state.hizli_soru = ""
            st.session_state.sohbet_mesajlari.append({"role": "user", "content": soru})
            with st.spinner("AI cevap yaziyor..." if tr else "AI is typing..."):
                try:
                    cevap = ai_soru_cevap(soru, st.session_state.cv_text, st.session_state.jd_text, st.session_state.mesaj_gecmisi, tr)
                    st.session_state.mesaj_gecmisi.append({"role": "user", "content": soru})
                    st.session_state.mesaj_gecmisi.append({"role": "assistant", "content": cevap})
                    st.session_state.sohbet_mesajlari.append({"role": "assistant", "content": cevap})
                except:
                    st.session_state.sohbet_mesajlari.append({"role": "assistant", "content": "Hata olustu." if tr else "An error occurred."})
            st.rerun()

        chat_placeholder = "Bir soru sorun..." if tr else "Ask a question..."
        if kullanici_sorusu := st.chat_input(chat_placeholder):
            st.session_state.sohbet_mesajlari.append({"role": "user", "content": kullanici_sorusu})
            with st.spinner("AI cevap yaziyor..." if tr else "AI is typing..."):
                try:
                    cevap = ai_soru_cevap(kullanici_sorusu, st.session_state.cv_text, st.session_state.jd_text, st.session_state.mesaj_gecmisi, tr)
                    st.session_state.mesaj_gecmisi.append({"role": "user", "content": kullanici_sorusu})
                    st.session_state.mesaj_gecmisi.append({"role": "assistant", "content": cevap})
                    st.session_state.sohbet_mesajlari.append({"role": "assistant", "content": cevap})
                except:
                    st.session_state.sohbet_mesajlari.append({"role": "assistant", "content": "Hata olustu." if tr else "An error occurred."})
            st.rerun()

        st.divider()
        st.caption("Groq AI (LLaMA 3.3 70B) ile analiz edilmistir. Sonuclar tavsiye niteligindedir.")


if __name__ == "__main__":
    main()
