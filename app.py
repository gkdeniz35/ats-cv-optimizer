"""
CV ATS ANALİZİ - Streamlit Web Application
Tamamen ücretsiz, Kural bazlı keyword eşleştirme ile ATS analizi yapar.
"""

import streamlit as st
import re
import io
from collections import Counter

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


# ──────────────────────────────────────────────
# DOSYA OKUMA
# ──────────────────────────────────────────────

def parse_pdf(file_bytes):
    if not PDF_SUPPORT:
        st.error("pdfplumber yüklü değil.")
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
        st.error("python-docx yüklü değil.")
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
        st.error("Desteklenmeyen dosya türü.")
        return ""


# ──────────────────────────────────────────────
# ANALİZ FONKSİYONLARI
# ──────────────────────────────────────────────

def temizle(text):
    """Metni küçük harfe çevir ve noktalama işaretlerini kaldır."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    return text


def kelimeleri_cıkar(text):
    """Metindeki anlamlı kelimeleri çıkar."""
    stopwords = {
        've', 'veya', 'ile', 'bir', 'bu', 'da', 'de', 'için', 'olan',
        'the', 'and', 'or', 'is', 'in', 'at', 'of', 'to', 'a', 'an',
        'for', 'on', 'with', 'as', 'by', 'be', 'are', 'was', 'were',
        'that', 'this', 'it', 'we', 'you', 'he', 'she', 'they', 'have',
        'has', 'had', 'will', 'would', 'can', 'could', 'should', 'may',
        'might', 'must', 'shall', 'do', 'does', 'did', 'not', 'but',
        'if', 'then', 'than', 'so', 'from', 'up', 'about', 'into',
        'through', 'during', 'including', 'until', 'against', 'among',
        'throughout', 'despite', 'towards', 'upon', 'concerning'
    }
    kelimeler = temizle(text).split()
    return [k for k in kelimeler if len(k) > 2 and k not in stopwords]


def bolum_tespit(cv_text):
    """CV'deki bölümleri tespit et."""
    text_lower = cv_text.lower()
    bolumler = {
        "experience": any(k in text_lower for k in ["experience", "deneyim", "iş deneyimi", "work", "employment", "çalıştım"]),
        "education": any(k in text_lower for k in ["education", "eğitim", "okul", "university", "üniversite", "mezun", "degree", "lisans"]),
        "skills": any(k in text_lower for k in ["skills", "yetenekler", "beceriler", "yetkinlikler", "competencies", "technical"]),
        "certifications": any(k in text_lower for k in ["certification", "sertifika", "certificate", "lisans", "license"])
    }
    return bolumler


def format_sorunlari_tespit(cv_text):
    """ATS'yi bozabilecek format sorunlarını tespit et."""
    sorunlar = []
    satirlar = cv_text.split('\n')

    # Çok kısa satırlar (tablo formatı)
    kisa_satirlar = [s for s in satirlar if 0 < len(s.strip()) < 15]
    if len(kisa_satirlar) > 10:
        sorunlar.append("CV'niz tablo veya sütun formatı içeriyor olabilir. ATS sistemleri tabloları okuyamaz.")

    # Çok uzun paragraflar
    uzun_satirlar = [s for s in satirlar if len(s.strip()) > 300]
    if uzun_satirlar:
        sorunlar.append("Çok uzun paragraflar var. Bullet point kullanmanız önerilir.")

    # Bölüm başlıklarının olmaması
    bolumler = bolum_tespit(cv_text)
    if not bolumler["skills"]:
        sorunlar.append("'Skills' veya 'Yetenekler' bölümü bulunamadı. ATS sistemleri bu bölümü arar.")
    if not bolumler["experience"]:
        sorunlar.append("'Experience' veya 'Deneyim' bölümü bulunamadı.")

    # Özel karakterler
    if any(c in cv_text for c in ['★', '●', '◆', '▸', '✦']):
        sorunlar.append("Özel karakterler (★, ●, ◆ vb.) ATS sistemlerinde hatalı okunabilir.")

    # Email kontrolü
    if not re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', cv_text):
        sorunlar.append("CV'de email adresi bulunamadı.")

    # Telefon kontrolü
    if not re.search(r'[\+]?[\d\s\-\(\)]{10,}', cv_text):
        sorunlar.append("CV'de telefon numarası bulunamadı.")

    return sorunlar


def keyword_analizi(cv_text, jd_text):
    """JD ile CV arasındaki keyword eşleşmesini analiz et."""
    cv_kelimeler = set(kelimeleri_cıkar(cv_text))
    jd_kelimeler = kelimeleri_cıkar(jd_text)

    # JD'deki en sık geçen kelimeleri bul
    jd_sayac = Counter(jd_kelimeler)
    onemli_jd_kelimeleri = {k for k, v in jd_sayac.items() if v >= 1 and len(k) > 3}

    # Eşleşenler ve eşleşmeyenler
    eslesen = onemli_jd_kelimeleri & cv_kelimeler
    eksik = onemli_jd_kelimeleri - cv_kelimeler

    # En önemli eksik kelimeleri filtrele (çok genel olanları çıkar)
    genel_kelimeler = {
        'olarak', 'olan', 'veya', 'ile', 'için', 'olan', 'must', 'will',
        'work', 'good', 'well', 'able', 'also', 'more', 'than', 'our',
        'your', 'their', 'have', 'been', 'they', 'from', 'such', 'both',
        'each', 'need', 'new', 'high', 'other', 'some', 'what', 'when',
        'where', 'which', 'while', 'how', 'all', 'any', 'use', 'used'
    }
    eksik = {k for k in eksik if k not in genel_kelimeler and len(k) > 3}

    return list(eslesen), list(eksik)[:15]


def zayif_bullet_tespit(cv_text):
    """Zayıf bullet point'leri tespit et."""
    zayif_ifadeler = [
        ("responsible for", "Led, managed veya delivered ile başlayın"),
        ("helped with", "Direkt katkınızı belirtin (örn: 'Developed', 'Built')"),
        ("worked on", "Somut eylemleri kullanın (örn: 'Implemented', 'Designed')"),
        ("assisted in", "Kendi başarılarınızı ön plana çıkarın"),
        ("sorumlu oldum", "Yönetme veya geliştirme gibi güçlü fiiller kullanın"),
        ("yardım ettim", "Direkt katkınızı belirtin"),
        ("çalıştım", "Başardığınız sonuçları yazın"),
        ("görev yaptım", "Somut başarılar ekleyin"),
    ]

    bulunan = []
    satirlar = cv_text.split('\n')
    for satir in satirlar:
        satir_lower = satir.lower().strip()
        for ifade, oneri in zayif_ifadeler:
            if ifade in satir_lower and len(satir.strip()) > 10:
                bulunan.append({
                    "original": satir.strip()[:100],
                    "issue": f"'{ifade}' ifadesi zayıf bir anlatım",
                    "suggestion": f"{oneri}. Sayısal sonuçlar ekleyin (örn: %20 artış sağladım)"
                })
                break
    return bulunan[:5]


def puan_hesapla(cv_text, jd_text, bolumler, eslesen_keywords, format_sorunlari):
    """ATS uyumluluk puanını hesapla."""
    puan = 0
    breakdown = {}

    # 1. Keyword eşleşmesi (30 puan)
    cv_kelimeler = set(kelimeleri_cıkar(cv_text))
    jd_kelimeler = set(kelimeleri_cıkar(jd_text))
    if jd_kelimeler:
        oran = len(set(eslesen_keywords)) / max(len(jd_kelimeler), 1)
        kw_puan = min(30, int(oran * 120))
    else:
        kw_puan = 15
    breakdown["keyword_match"] = kw_puan
    puan += kw_puan

    # 2. Bölüm yapısı (20 puan)
    bolum_puan = sum(5 for v in bolumler.values() if v)
    breakdown["section_structure"] = bolum_puan
    puan += bolum_puan

    # 3. Bullet kalitesi (20 puan)
    bullet_sayisi = len(re.findall(r'[\•\-\*]|\n\s*[-•]', cv_text))
    bullet_puan = min(20, bullet_sayisi * 2)
    breakdown["bullet_quality"] = bullet_puan
    puan += bullet_puan

    # 4. Format (15 puan)
    format_puan = max(0, 15 - len(format_sorunlari) * 3)
    breakdown["formatting"] = format_puan
    puan += format_puan

    # 5. Sayısal başarılar (15 puan)
    sayisal = re.findall(r'\d+\s*(%|yıl|ay|kişi|milyon|bin|proje|müşteri|year|month|people|million|k\b)', cv_text.lower())
    sayisal_puan = min(15, len(sayisal) * 3)
    breakdown["quantified_achievements"] = sayisal_puan
    puan += sayisal_puan

    return min(100, puan), breakdown


def ozet_olustur(puan, bolumler, eslesen, eksik, format_sorunlari):
    """Genel özet oluştur."""
    guclu = sum(1 for v in bolumler.values() if v)
    if puan >= 75:
        return f"CV'niz bu pozisyon için güçlü bir uyum gösteriyor ({puan}/100). {len(eslesen)} anahtar kelime eşleşti. Küçük iyileştirmelerle daha da güçlendirebilirsiniz."
    elif puan >= 50:
        return f"CV'niz orta düzeyde uyumlu ({puan}/100). {len(eksik)} önemli kelime eksik. Bu kelimeleri ekleyerek puanınızı artırabilirsiniz."
    else:
        return f"CV'niz bu pozisyon için düşük uyum gösteriyor ({puan}/100). İş ilanındaki anahtar kelimeleri CV'nize eklemeniz ve format sorunlarını gidermeniz önerilir."


def iyilestirme_onerileri(bolumler, eksik, format_sorunlari, cv_text):
    """Somut iyileştirme önerileri oluştur."""
    oneriler = []

    if eksik:
        oneriler.append(f"Şu eksik anahtar kelimeleri CV'nize ekleyin: {', '.join(eksik[:5])}")

    if not bolumler["skills"]:
        oneriler.append("'Beceriler' veya 'Skills' başlıklı bir bölüm ekleyin ve teknik yeteneklerinizi listeleyin.")

    if not bolumler["certifications"]:
        oneriler.append("Varsa sertifikalarınızı ve eğitimlerinizi ayrı bir bölümde belirtin.")

    sayisal = re.findall(r'\d+', cv_text)
    if len(sayisal) < 3:
        oneriler.append("Başarılarınızı sayısal verilerle destekleyin (örn: '%20 satış artışı', '50 kişilik ekip yönettim').")

    if format_sorunlari:
        oneriler.append("Format sorunlarını giderin: " + format_sorunlari[0])

    oneriler.append("Her iş ilanı için CV'nizi özelleştirin ve ilandaki kelimeleri birebir kullanın.")

    return oneriler[:5]


# ──────────────────────────────────────────────
# GÖRSEL YARDIMCILAR
# ──────────────────────────────────────────────

def score_color(score):
    if score >= 75:
        return "#2ecc71"
    elif score >= 50:
        return "#f39c12"
    else:
        return "#e74c3c"


def render_score_gauge(score):
    color = score_color(score)
    if score >= 75:
        label = "Güçlü Eşleşme ✅"
    elif score >= 50:
        label = "Orta Eşleşme ⚠️"
    else:
        label = "Zayıf Eşleşme ❌"
    filled = int(score / 5)
    empty = 20 - filled
    bar = "█" * filled + "░" * empty
    st.markdown(
        f"<h1 style='color:{color}; font-size:3rem;'>{score}/100</h1>"
        f"<p style='font-family:monospace; letter-spacing:2px; color:{color};'>{bar}</p>"
        f"<p style='font-size:1.2rem;'>{label}</p>",
        unsafe_allow_html=True
    )


# ──────────────────────────────────────────────
# ANA UYGULAMA
# ──────────────────────────────────────────────

def main():
    st.set_page_config(page_title="ATS CV Optimizer", page_icon="📄", layout="wide")

    st.title("📄 ATS CV Optimizer")
    st.caption("Ücretsiz ATS uyumluluk analizi — CV'nizi iş ilanına göre optimize edin")
    st.divider()

    with st.sidebar:
        st.header("ℹ️ Nasıl Çalışır?")
        st.markdown("1. CV'nizi yapıştırın veya yükleyin\n2. İş ilanını yapıştırın\n3. **Analiz Et** butonuna basın\n4. Sonuçları inceleyin")
        st.markdown("---")
        st.success("✅ Tamamen ücretsiz\n\n✅ API key gerektirmez\n\n✅ Verileriniz kayıt edilmez")

    col_cv, col_jd = st.columns(2)

    with col_cv:
        st.subheader("📋 CV'niz")
        input_method = st.radio("Giriş yöntemi", ["Metin yapıştır", "Dosya yükle (PDF / DOCX)"], horizontal=True)
        cv_text = ""
        if input_method == "Metin yapıştır":
            cv_text = st.text_area("CV'nizi buraya yapıştırın", height=350, placeholder="Ad Soyad\nemail@gmail.com\n\nDENEYİM\n...")
        else:
            uploaded = st.file_uploader("CV Yükle", type=["pdf", "docx"], label_visibility="collapsed")
            if uploaded:
                with st.spinner("Dosya okunuyor..."):
                    cv_text = extract_text_from_upload(uploaded)
                if cv_text:
                    st.success(f"{len(cv_text.split())} kelime okundu.")
                    with st.expander("Önizleme"):
                        st.text(cv_text[:2000])

    with col_jd:
        st.subheader("🎯 İş İlanı")
        jd_text = st.text_area("İş ilanını buraya yapıştırın", height=350, placeholder="Aradığımız kişi en az 2 yıl deneyimli...")

    st.divider()
    analyze_btn = st.button("🔍 CV'yi Analiz Et", type="primary", use_container_width=True)

    if analyze_btn:
        if not cv_text.strip():
            st.error("Lütfen CV'nizi girin.")
            st.stop()
        if not jd_text.strip():
            st.error("Lütfen iş ilanını girin.")
            st.stop()

        with st.spinner("Analiz ediliyor..."):
            bolumler = bolum_tespit(cv_text)
            eslesen, eksik = keyword_analizi(cv_text, jd_text)
            format_sorunlari = format_sorunlari_tespit(cv_text)
            zayif_bulletlar = zayif_bullet_tespit(cv_text)
            puan, breakdown = puan_hesapla(cv_text, jd_text, bolumler, eslesen, format_sorunlari)
            ozet = ozet_olustur(puan, bolumler, eslesen, eksik, format_sorunlari)
            oneriler = iyilestirme_onerileri(bolumler, eksik, format_sorunlari, cv_text)

        st.success("Analiz tamamlandı!")
        st.divider()
        st.header("📊 ATS Analiz Raporu")

        r1, r2 = st.columns([1, 2])
        with r1:
            st.subheader("ATS Uyumluluk Puanı")
            render_score_gauge(puan)

        with r2:
            st.subheader("Puan Dağılımı")
            labels = {
                "keyword_match": "Keyword Eşleşmesi (30)",
                "section_structure": "Bölüm Yapısı (20)",
                "bullet_quality": "Bullet Kalitesi (20)",
                "formatting": "Format (15)",
                "quantified_achievements": "Sayısal Başarılar (15)"
            }
            import re as re2
            for key, label in labels.items():
                val = breakdown.get(key, 0)
                max_val = int(re2.search(r"\((\d+)\)", label).group(1))
                pct = min(100, int((val / max_val) * 100)) if max_val else 0
                st.write(f"**{label}**: {val}/{max_val}")
                st.progress(pct)

        st.divider()
        st.subheader("📁 CV Bölümleri")
        s_cols = st.columns(4)
        bolum_isimleri = {"experience": "Deneyim", "education": "Eğitim", "skills": "Beceriler", "certifications": "Sertifikalar"}
        for i, (key, isim) in enumerate(bolum_isimleri.items()):
            s_cols[i].metric(label=isim, value="✅" if bolumler.get(key) else "❌")

        st.divider()
        st.subheader("🗒️ Genel Değerlendirme")
        st.info(ozet)

        st.subheader("🚀 Top 5 İyileştirme Önerisi")
        for i, tip in enumerate(oneriler, 1):
            st.markdown(f"**{i}.** {tip}")

        st.divider()
        col_kw, col_fmt = st.columns(2)

        with col_kw:
            st.subheader("🔑 Eksik Anahtar Kelimeler")
            if eksik:
                tags_html = " ".join(
                    f"<span style='background:#fff3cd; border:1px solid #ffc107; border-radius:4px; padding:2px 8px; margin:2px; display:inline-block;'>🏷️ {kw}</span>"
                    for kw in eksik
                )
                st.markdown(tags_html, unsafe_allow_html=True)
            else:
                st.success("Kritik eksik kelime bulunamadı.")

            st.markdown("---")
            st.subheader("✅ Eşleşen Kelimeler")
            if eslesen:
                tags_html = " ".join(
                    f"<span style='background:#d4edda; border:1px solid #28a745; border-radius:4px; padding:2px 8px; margin:2px; display:inline-block;'>✓ {kw}</span>"
                    for kw in eslesen[:20]
                )
                st.markdown(tags_html, unsafe_allow_html=True)

        with col_fmt:
            st.subheader("⚠️ Format Sorunları")
            if format_sorunlari:
                for sorun in format_sorunlari:
                    st.warning(sorun)
            else:
                st.success("Büyük format sorunu bulunamadı.")

        st.divider()
        st.subheader("✍️ Zayıf İfadeler ve Öneriler")
        if zayif_bulletlar:
            for idx, item in enumerate(zayif_bulletlar, 1):
                with st.expander(f"İfade {idx}: {item['original'][:60]}..."):
                    st.markdown(f"**Orijinal:** _{item['original']}_")
                    st.markdown(f"**Sorun:** {item['issue']}")
                    st.markdown(
                        f"<div style='background:#d4edda; padding:10px; border-radius:6px;'>"
                        f"✅ <strong>Öneri:</strong> {item['suggestion']}</div>",
                        unsafe_allow_html=True
                    )
        else:
            st.success("Zayıf ifade bulunamadı.")

        st.divider()
        st.caption("Analiz kural bazlı keyword eşleştirme ile yapılmıştır. Sonuçlar tavsiye niteliğindedir.")


if __name__ == "__main__":
    main()

