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


def kelimeleri_cikar(text):
    stopwords = {
        've', 'veya', 'ile', 'bir', 'bu', 'da', 'de', 'icin', 'olan',
        'the', 'and', 'or', 'is', 'in', 'at', 'of', 'to', 'a', 'an',
        'for', 'on', 'with', 'as', 'by', 'be', 'are', 'was', 'were',
        'that', 'this', 'it', 'we', 'you', 'he', 'she', 'they', 'have',
        'has', 'had', 'will', 'would', 'can', 'could', 'should', 'may',
        'might', 'must', 'shall', 'do', 'does', 'did', 'not', 'but',
        'if', 'then', 'than', 'so', 'from', 'up', 'about', 'into'
    }
    kelimeler = temizle(text).split()
    return [k for k in kelimeler if len(k) > 2 and k not in stopwords]


def bolum_tespit(cv_text):
    text_lower = cv_text.lower()
    return {
        "experience": any(k in text_lower for k in ["experience", "deneyim", "work", "employment", "calistim"]),
        "education": any(k in text_lower for k in ["education", "egitim", "university", "universite", "mezun", "degree", "lisans"]),
        "skills": any(k in text_lower for k in ["skills", "yetenekler", "beceriler", "competencies", "technical"]),
        "certifications": any(k in text_lower for k in ["certification", "sertifika", "certificate", "license"])
    }


def format_sorunlari_tespit(cv_text):
    sorunlar = []
    satirlar = cv_text.split('\n')
    kisa_satirlar = [s for s in satirlar if 0 < len(s.strip()) < 15]
    if len(kisa_satirlar) > 10:
        sorunlar.append("CV'niz tablo veya sutun formati iceriyor. ATS sistemleri tablolari okuyamaz.")
    bolumler = bolum_tespit(cv_text)
    if not bolumler["skills"]:
        sorunlar.append("'Skills' veya 'Yetenekler' bolumu bulunamadi.")
    if not bolumler["experience"]:
        sorunlar.append("'Experience' veya 'Deneyim' bolumu bulunamadi.")
    if not re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', cv_text):
        sorunlar.append("CV'de email adresi bulunamadi.")
    if not re.search(r'[\+]?[\d\s\-\(\)]{10,}', cv_text):
        sorunlar.append("CV'de telefon numarasi bulunamadi.")
    return sorunlar


def keyword_analizi(cv_text, jd_text):
    cv_kelimeler = set(kelimeleri_cikar(cv_text))
    jd_kelimeler = kelimeleri_cikar(jd_text)
    jd_sayac = Counter(jd_kelimeler)
    onemli_jd = {k for k, v in jd_sayac.items() if len(k) > 3}
    eslesen = onemli_jd & cv_kelimeler
    eksik = onemli_jd - cv_kelimeler
    genel = {'must', 'will', 'work', 'good', 'well', 'able', 'also', 'more',
             'than', 'our', 'your', 'their', 'have', 'been', 'they', 'from',
             'such', 'both', 'each', 'need', 'new', 'high', 'other', 'some',
             'what', 'when', 'where', 'which', 'while', 'how', 'all', 'any'}
    eksik = {k for k in eksik if k not in genel and len(k) > 3}
    return list(eslesen), list(eksik)[:15]


def puan_hesapla(cv_text, jd_text, bolumler, eslesen, format_sorunlari):
    puan = 0
    breakdown = {}
    jd_kelimeler = set(kelimeleri_cikar(jd_text))
    kw_puan = min(30, int(len(set(eslesen)) / max(len(jd_kelimeler), 1) * 120)) if jd_kelimeler else 15
    breakdown["keyword_match"] = kw_puan
    puan += kw_puan
    bolum_puan = sum(5 for v in bolumler.values() if v)
    breakdown["section_structure"] = bolum_puan
    puan += bolum_puan
    bullet_sayisi = len(re.findall(r'[\*\-]|\n\s*[-*]', cv_text))
    bullet_puan = min(20, bullet_sayisi * 2)
    breakdown["bullet_quality"] = bullet_puan
    puan += bullet_puan
    format_puan = max(0, 15 - len(format_sorunlari) * 3)
    breakdown["formatting"] = format_puan
    puan += format_puan
    sayisal = re.findall(r'\d+\s*(%|yil|ay|kisi|milyon|bin|proje|year|month|people|million)', cv_text.lower())
    sayisal_puan = min(15, len(sayisal) * 3)
    breakdown["quantified_achievements"] = sayisal_puan
    puan += sayisal_puan
    return min(100, puan), breakdown


def ai_feedback_olustur(cv_text, jd_text, puan, eksik, format_sorunlari):
    """AI ile detayli feedback olustur."""
    client = get_groq_client()
    
    prompt = f"""Sen bir kariyer kocu ve CV uzmanisın. Asagidaki CV'yi analiz et ve Turkce olarak geri bildirim ver.

CV:
{cv_text[:3000]}

Is Ilani:
{jd_text[:2000]}

ATS Puani: {puan}/100
Eksik Kelimeler: {', '.join(eksik[:10]) if eksik else 'Yok'}
Format Sorunlari: {', '.join(format_sorunlari[:3]) if format_sorunlari else 'Yok'}

Lutfen su konularda Turkce detayli geri bildirim ver:
1. CV'nin guclu yonleri
2. Mutlaka duzeltilmesi gereken eksikler
3. Bu is icin ozgul tavsiyeler
4. Mulakat hazirlik ipuclari
5. Genel kariyer tavsiyesi

Samimi, yardimci ve motive edici bir dille yaz. Her madde icin somut ornekler ver."""

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1500,
    )
    return response.choices[0].message.content


def ai_soru_cevap(soru, cv_text, jd_text, mesaj_gecmisi):
    """Kullanicinin sorularini AI ile cevapla."""
    client = get_groq_client()
    
    sistem_mesaji = f"""Sen bir kariyer kocu ve CV uzmanisın. Kullanicinin CV'si ve basvurdugu is ilani hakkinda Turkce olarak yardimci oluyorsun.

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

    st.title("📄 ATS CV Optimizer")
    st.caption("AI destekli CV analizi ve kariyer kocu — Is ilanina gore CV'nizi optimize edin")
    st.divider()

    with st.sidebar:
        st.header("Nasil Calisir?")
        st.markdown("1. CV'nizi yapistirin veya yukleyin\n2. Is ilanini yapistirin\n3. **Analiz Et** butonuna basin\n4. AI feedback ve skor alin\n5. AI bota soru sorun")
        st.markdown("---")
        st.success("✅ Tamamen ucretsiz\n\n✅ API key gerektirmez\n\n✅ AI destekli analiz")

    # Session state
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

    col_cv, col_jd = st.columns(2)

    with col_cv:
        st.subheader("📋 CV'niz")
        input_method = st.radio("Giris yontemi", ["Metin yapistir", "Dosya yukle (PDF / DOCX)"], horizontal=True)
        cv_text = ""
        if input_method == "Metin yapistir":
            cv_text = st.text_area("CV'nizi buraya yapistirin", height=300, placeholder="Ad Soyad\nemail@gmail.com\n\nDENEYIM\n...")
        else:
            uploaded = st.file_uploader("CV Yukle", type=["pdf", "docx"], label_visibility="collapsed")
            if uploaded:
                with st.spinner("Dosya okunuyor..."):
                    cv_text = extract_text_from_upload(uploaded)
                if cv_text:
                    st.success(f"{len(cv_text.split())} kelime okundu.")

    with col_jd:
        st.subheader("🎯 Is Ilani")
        jd_text = st.text_area("Is ilanini buraya yapistirin", height=300, placeholder="Aradigimiz kisi en az 2 yil deneyimli...")

    st.divider()
    analyze_btn = st.button("🔍 CV'yi Analiz Et", type="primary", use_container_width=True)

    if analyze_btn:
        if not cv_text.strip():
            st.error("Lutfen CV'nizi girin.")
            st.stop()
        if not jd_text.strip():
            st.error("Lutfen is ilanini girin.")
            st.stop()

        st.session_state.cv_text = cv_text
        st.session_state.jd_text = jd_text
        st.session_state.mesaj_gecmisi = []
        st.session_state.sohbet_mesajlari = []

        with st.spinner("Analiz ediliyor..."):
            bolumler = bolum_tespit(cv_text)
            eslesen, eksik = keyword_analizi(cv_text, jd_text)
            format_sorunlari = format_sorunlari_tespit(cv_text)
            puan, breakdown = puan_hesapla(cv_text, jd_text, bolumler, eslesen, format_sorunlari)

        with st.spinner("AI feedback hazirlaniyor..."):
            try:
                ai_feedback = ai_feedback_olustur(cv_text, jd_text, puan, eksik, format_sorunlari)
            except Exception as e:
                ai_feedback = "AI feedback su an hazirlanamadi. Lutfen tekrar deneyin."

        st.session_state.analiz_yapildi = True
        st.session_state.bolumler = bolumler
        st.session_state.eslesen = eslesen
        st.session_state.eksik = eksik
        st.session_state.format_sorunlari = format_sorunlari
        st.session_state.puan = puan
        st.session_state.breakdown = breakdown
        st.session_state.ai_feedback = ai_feedback

    # Analiz sonuclari
    if st.session_state.analiz_yapildi:
        puan = st.session_state.puan
        breakdown = st.session_state.breakdown
        bolumler = st.session_state.bolumler
        eslesen = st.session_state.eslesen
        eksik = st.session_state.eksik
        format_sorunlari = st.session_state.format_sorunlari
        ai_feedback = st.session_state.ai_feedback

        st.success("Analiz tamamlandi!")
        st.divider()
        st.header("📊 ATS Analiz Raporu")

        r1, r2 = st.columns([1, 2])
        with r1:
            st.subheader("ATS Puani")
            render_score_gauge(puan)

        with r2:
            st.subheader("Puan Dagilimi")
            labels = {
                "keyword_match": "Keyword Eslesmesi (30)",
                "section_structure": "Bolum Yapisi (20)",
                "bullet_quality": "Bullet Kalitesi (20)",
                "formatting": "Format (15)",
                "quantified_achievements": "Sayisal Basarilar (15)"
            }
            for key, label in labels.items():
                val = breakdown.get(key, 0)
                max_val = int(re.search(r"\((\d+)\)", label).group(1))
                pct = min(100, int((val / max_val) * 100)) if max_val else 0
                st.write(f"**{label}**: {val}/{max_val}")
                st.progress(pct)

        st.divider()

        # AI FEEDBACK BOLUMU
        st.subheader("🤖 AI Kariyer Kocu Feedback")
        st.markdown(
            f"<div style='background:#f8f9ff; border-left:4px solid #4a90e2; padding:20px; border-radius:8px; line-height:1.8;'>{ai_feedback}</div>",
            unsafe_allow_html=True
        )

        st.divider()

        # Keyword analizi
        col_kw, col_fmt = st.columns(2)
        with col_kw:
            st.subheader("🔑 Eksik Kelimeler")
            if eksik:
                tags_html = " ".join(
                    f"<span style='background:#fff3cd; border:1px solid #ffc107; border-radius:4px; padding:2px 8px; margin:2px; display:inline-block;'>🏷️ {kw}</span>"
                    for kw in eksik
                )
                st.markdown(tags_html, unsafe_allow_html=True)
            else:
                st.success("Kritik eksik kelime bulunamadi.")
            st.markdown("---")
            st.subheader("✅ Eslesen Kelimeler")
            if eslesen:
                tags_html = " ".join(
                    f"<span style='background:#d4edda; border:1px solid #28a745; border-radius:4px; padding:2px 8px; margin:2px; display:inline-block;'>✓ {kw}</span>"
                    for kw in eslesen[:20]
                )
                st.markdown(tags_html, unsafe_allow_html=True)

        with col_fmt:
            st.subheader("⚠️ Format Sorunlari")
            if format_sorunlari:
                for sorun in format_sorunlari:
                    st.warning(sorun)
            else:
                st.success("Buyuk format sorunu bulunamadi.")

        st.divider()

        # AI SOHBET BOTU
        st.subheader("💬 AI Kariyer Asistani")
        st.markdown("CV'niz hakkinda soru sorun! Cover letter, mulakat hazirlik, maas tavsiyesi...")

        # Hizli sorular
        st.markdown("**Hizli Sorular:**")
        hizli_col1, hizli_col2, hizli_col3 = st.columns(3)
        
        with hizli_col1:
            if st.button("📝 Cover Letter Yaz", use_container_width=True):
                st.session_state.hizli_soru = "Bu is icin bana Turkce bir cover letter yazar misin?"
        with hizli_col2:
            if st.button("🎯 Mulakat Sorulari", use_container_width=True):
                st.session_state.hizli_soru = "Bu is icin hangi mulakat sorulari gelebilir ve nasil cevaplamaliyim?"
        with hizli_col3:
            if st.button("💰 Maas Tavsiyesi", use_container_width=True):
                st.session_state.hizli_soru = "Bu pozisyon icin Turkiye'de ne kadar maas beklentisi olmali?"

        # Sohbet gecmisi goster
        for mesaj in st.session_state.sohbet_mesajlari:
            with st.chat_message(mesaj["role"]):
                st.markdown(mesaj["content"])

        # Hizli soru varsa otomatik gonder
        if "hizli_soru" in st.session_state and st.session_state.hizli_soru:
            soru = st.session_state.hizli_soru
            st.session_state.hizli_soru = ""
            
            st.session_state.sohbet_mesajlari.append({"role": "user", "content": soru})
            
            with st.spinner("AI cevap yaziyor..."):
                try:
                    cevap = ai_soru_cevap(
                        soru,
                        st.session_state.cv_text,
                        st.session_state.jd_text,
                        st.session_state.mesaj_gecmisi
                    )
                    st.session_state.mesaj_gecmisi.append({"role": "user", "content": soru})
                    st.session_state.mesaj_gecmisi.append({"role": "assistant", "content": cevap})
                    st.session_state.sohbet_mesajlari.append({"role": "assistant", "content": cevap})
                except Exception as e:
                    cevap = "Bir hata olustu. Lutfen tekrar deneyin."
                    st.session_state.sohbet_mesajlari.append({"role": "assistant", "content": cevap})
            st.rerun()

        # Manuel soru girisi
        if kullanici_sorusu := st.chat_input("Bir soru sorun... (ornek: 'Bu is icin cover letter yazar misin?')"):
            st.session_state.sohbet_mesajlari.append({"role": "user", "content": kullanici_sorusu})

            with st.spinner("AI cevap yaziyor..."):
                try:
                    cevap = ai_soru_cevap(
                        kullanici_sorusu,
                        st.session_state.cv_text,
                        st.session_state.jd_text,
                        st.session_state.mesaj_gecmisi
                    )
                    st.session_state.mesaj_gecmisi.append({"role": "user", "content": kullanici_sorusu})
                    st.session_state.mesaj_gecmisi.append({"role": "assistant", "content": cevap})
                    st.session_state.sohbet_mesajlari.append({"role": "assistant", "content": cevap})
                except Exception as e:
                    cevap = "Bir hata olustu. Lutfen tekrar deneyin."
                    st.session_state.sohbet_mesajlari.append({"role": "assistant", "content": cevap})
            st.rerun()

        st.divider()
        st.caption("AI analizi tavsiye niteligindedir. Groq AI (LLaMA 3.3 70B) kullanilmaktadir.")


if __name__ == "__main__":
    main()
