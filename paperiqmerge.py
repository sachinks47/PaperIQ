import streamlit as st
import pdfplumber
import docx
import re
import numpy as np
import plotly.graph_objects as go
import heapq
import sqlite3
import hashlib
from collections import Counter
from textblob import TextBlob
from fpdf import FPDF

# -----------------------------
# Database Setup
# -----------------------------
def init_db():
    conn = sqlite3.connect('paperiq_users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, gmail TEXT, password TEXT, role TEXT)''')
    conn.commit()
    conn.close()

def add_user(username, gmail, password, role):
    conn = sqlite3.connect('paperiq_users.db')
    c = conn.cursor()
    hashed_pwd = hashlib.sha256(password.encode()).hexdigest()
    try:
        c.execute("INSERT INTO users VALUES (?,?,?,?)", (username, gmail, hashed_pwd, role))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()

def verify_user(username, password):
    conn = sqlite3.connect('paperiq_users.db')
    c = conn.cursor()
    hashed_pwd = hashlib.sha256(password.encode()).hexdigest()
    c.execute("SELECT gmail, role FROM users WHERE username=? AND password=?", (username, hashed_pwd))
    result = c.fetchone()
    conn.close()
    return result

# Initialize DB on start
init_db()

# -----------------------------
# Configuration & Styling
# -----------------------------
st.set_page_config(page_title="PaperIQ", page_icon="🔬", layout="wide")

# Session State Initialization
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'auth_mode' not in st.session_state:
    st.session_state.auth_mode = "login"
if 'user_data' not in st.session_state:
    st.session_state.user_data = {}
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'summary_length_slider' not in st.session_state:
    st.session_state.summary_length_slider = "Medium"

# CSS Styling
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');

        [data-testid="stAppViewContainer"] {
            background: radial-gradient(circle at top right, #1a1c23, #0e1117);
            color: #ffffff;
            font-family: 'Inter', sans-serif;
        }

        .main-header { 
            text-align: center; 
            background: linear-gradient(90deg, #90EE90, #ffffff);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-top: 1rem;
            margin-bottom: 0px; 
            font-size: 4rem; 
            font-weight: 800;
            letter-spacing: -2px;
        }
        
        .sub-header { 
            text-align: center; 
            color: rgba(255, 255, 255, 0.7); 
            margin-bottom: 40px; 
            font-size: 1.1rem;
            font-weight: 300;
            letter-spacing: 1px;
        }

        .glass-panel { padding: 20px; max-width: 500px; margin: auto; }

        .metric-card {
            background: rgba(255, 255, 255, 0.05);
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            border-left: 4px solid #90EE90;
        }

        .metric-label { font-size: 0.8rem; text-transform: uppercase; color: rgba(255, 255, 255, 0.6); }
        .metric-value { font-size: 1.8rem; font-weight: 800; color: #ffffff; }
        .metric-caption { font-size: 0.75rem; color: #90EE90; margin-top: 4px; font-weight: 600; }

        .sidebar-title { 
            color: #90EE90; font-weight: 600; font-size: 1.4rem; 
            border-bottom: 2px solid rgba(144, 238, 144, 0.3);
            padding-bottom: 10px; margin-bottom: 20px;
        }

        .account-box {
            background: rgba(144, 238, 144, 0.05);
            padding: 15px; border-radius: 12px;
            border: 1px solid rgba(144, 238, 144, 0.2);
        }

        .word-pill {
            display: inline-block;
            background: rgba(144, 238, 144, 0.1);
            color: #90EE90;
            padding: 4px 10px;
            border-radius: 20px;
            margin: 4px;
            font-size: 0.85rem;
            border: 1px solid rgba(144, 238, 144, 0.3);
        }

        .role-tag {
            font-size: 0.7rem;
            background: #90EE90;
            color: #0e1117;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: bold;
            text-transform: uppercase;
        }

        .export-section {
            background: rgba(144, 238, 144, 0.03);
            border: 1px solid rgba(144, 238, 144, 0.1);
            border-radius: 15px;
            padding: 25px;
            text-align: center;
            margin-top: 30px;
        }
        
        .summary-box {
            background: rgba(144, 238, 144, 0.05);
            border: 1px solid rgba(144, 238, 144, 0.2);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 15px;
            transition: all 0.3s ease;
        }
        
        .summary-box:hover {
            background: rgba(144, 238, 144, 0.08);
            border-color: rgba(144, 238, 144, 0.4);
        }
        
        .summary-title {
            color: #90EE90;
            font-weight: 600;
            margin-bottom: 10px;
            font-size: 1.15rem;
            border-bottom: 1px dashed rgba(144, 238, 144, 0.2);
            padding-bottom: 8px;
        }
        
        .summary-content {
            color: #e0e0e0;
            line-height: 1.6;
            font-size: 0.95rem;
        }

        p, div, span, label, h3 { color: #ffffff; }
        [data-testid="stFileUploadDropzone"] {
            border: 1px dashed rgba(144, 238, 144, 0.2) !important;
            background: transparent !important;
        }
    </style>
""", unsafe_allow_html=True)

# -----------------------------
# Core Logic Functions
# -----------------------------

def get_frequent_keywords(text, n=12):
    stop_words = set(['the', 'and', 'that', 'with', 'from', 'this', 'their', 'which', 'were', 'also', 'been', 'used', 'these', 'could', 'would'])
    words = re.findall(r'\b[a-z]{4,}\b', text.lower())
    filtered = [w for w in words if w not in stop_words]
    return Counter(filtered).most_common(n)

def extractive_summarize(text, num_sentences=3):
    if not text or len(text.split()) < 50: return text
    blob = TextBlob(text)
    sentences = blob.sentences
    if len(sentences) <= num_sentences: return text
    
    word_freq = {}
    for word in blob.words:
        w = word.lower()
        if w.isalpha():
            word_freq[w] = word_freq.get(w, 0) + 1
            
    max_f = max(word_freq.values()) if word_freq else 1
    for w in word_freq: word_freq[w] /= max_f
    
    sent_scores = {}
    for sent in sentences:
        for word in sent.words:
            w = word.lower()
            if w in word_freq:
                sent_scores[sent] = sent_scores.get(sent, 0) + word_freq[w]
                
    top_sents = heapq.nlargest(num_sentences, sent_scores, key=sent_scores.get)
    return " ".join([str(s) for s in sorted(top_sents, key=lambda x: sentences.index(x))])

def calculate_readability(text):
    words = len(text.split())
    sents = text.count('.') + text.count('?') + 1
    if sents == 0 or words == 0: return 0
    # Simplified Flesch Reading Ease approximation
    score = 206.835 - 1.015 * (words / sents) - 84.6 * (1.5) 
    return max(0, min(100, score))

def analyze_linguistics(text):
    blob = TextBlob(text)
    words = blob.words
    sents = blob.sentences
    word_count = len(words)
    if word_count == 0: return None
    
    avg_sent_len = np.mean([len(s.words) for s in sents])
    avg_word_len = np.mean([len(w) for w in words]) if word_count > 0 else 0
    sentiment = blob.sentiment.polarity
    
    # Specific metric scores
    lang_score = min(100, (avg_sent_len * 1.2) + (50 + sentiment * 20))
    trans = ["however", "therefore", "thus", "consequently", "moreover"]
    coherence = min(100, (sum(text.lower().count(t) for t in trans) * 5) + 40)
    
    reasoning_keys = ["because", "since", "implies", "evidence", "result"]
    reasoning = min(100, (sum(text.lower().count(k) for k in reasoning_keys) * 4) + 35)
    
    sophistication = min(100, (len([w for w in words if len(w) > 7]) / word_count) * 400)
    readability = calculate_readability(text)
    
    composite = (lang_score * 0.3) + (coherence * 0.2) + (reasoning * 0.2) + (sophistication * 0.15) + (readability * 0.15)
    
    return {
        "metrics": {
            "Language": round(lang_score, 1),
            "Coherence": round(coherence, 1),
            "Reasoning": round(reasoning, 1),
            "Sophistication": round(sophistication, 1),
            "Readability": round(readability, 1),
            "Composite": round(composite, 1)
        },
        "stats": {
            "Word Count": word_count,
            "Sentences": len(sents),
            "Avg Sent Len": round(avg_sent_len, 2),
            "Avg Word Len": round(avg_word_len, 2),
            "Sentiment": round(sentiment, 2)
        },
        "long_sentences": [str(s) for s in sents if len(s.words) > 35][:5]
    }

def extract_sections_structured(file):
    data = {"Executive Summary": []}
    curr = "Executive Summary"
    text_content = ""
    
    if file.name.endswith(".pdf"):
        with pdfplumber.open(file) as pdf:
            for page in pdf.pages:
                lines = (page.extract_text() or "").split('\n')
                for line in lines:
                    clean = line.strip()
                    if not clean: continue
                    if (clean.isupper() and len(clean) < 60) or re.match(r'^\d+\.', clean):
                        curr = clean
                        data[curr] = []
                    else:
                        data[curr].append(clean)
                    text_content += clean + " "
    elif file.name.endswith(".docx"):
        doc = docx.Document(file)
        for para in doc.paragraphs:
            clean = para.text.strip()
            if not clean: continue
            if para.style.name.startswith('Heading') or clean.isupper():
                curr = clean
                data[curr] = []
            else:
                data[curr].append(clean)
            text_content += clean + " "
    else:
        text_content = file.getvalue().decode()
        data["Full Content"] = [text_content]

    raw_sections = {k: " ".join(v) for k, v in data.items() if v}
    return raw_sections, text_content

def create_pdf_report(results, filename):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"PaperIQ Analysis: {filename}", ln=True, align='C')
    pdf.ln(10)
    
    # 1. Linguistic Scores
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Composite Score: {results['metrics']['Composite']}/100", ln=True)
    pdf.ln(2)
    
    pdf.set_font("Arial", '', 10)
    for k, v in results['metrics'].items():
        if k != 'Composite': pdf.cell(0, 8, f"{k}: {v}/100", ln=True)
    pdf.ln(5)

    # 2. Text Statistics
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Text Statistics:", ln=True)
    pdf.ln(2)
    
    pdf.set_font("Arial", '', 10)
    for k, v in results['stats'].items():
        pdf.cell(0, 8, f"{k}: {v}", ln=True)
    pdf.ln(5)

    # 3. Section Summaries
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Section Breakdowns:", ln=True)
    pdf.ln(3)
    
    for title, summary in results['summaries'].items():
        pdf.set_font("Arial", 'B', 10)
        safe_title = title.encode('latin-1', 'replace').decode('latin-1')
        pdf.cell(0, 8, f"-> {safe_title}", ln=True)
        
        pdf.set_font("Arial", '', 10)
        safe_summary = summary.encode('latin-1', 'replace').decode('latin-1')
        pdf.multi_cell(0, 5, safe_summary)
        pdf.ln(4)
        
    return pdf.output(dest='S').encode('latin-1', 'replace')

# -----------------------------
# UI Components
# -----------------------------

def auth_page():
    st.markdown('<h1 class="main-header">PaperIQ</h1>', unsafe_allow_html=True)
    
    if st.session_state.auth_mode == "login":
        st.markdown('<p class="sub-header">Please sign in to continue</p>', unsafe_allow_html=True)
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        user = st.text_input("Username")
        pwd = st.text_input("Password", type="password")
        if st.button("Sign In", use_container_width=True):
            res = verify_user(user, pwd)
            if res:
                st.session_state.logged_in = True
                st.session_state.user_data = {"username": user, "gmail": res[0], "role": res[1]}
                st.rerun()
            else:
                st.error("Invalid credentials.")
        if st.button("Need an account? Sign Up", use_container_width=True):
            st.session_state.auth_mode = "signup"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    
    else:
        st.markdown('<p class="sub-header">Create your academic profile</p>', unsafe_allow_html=True)
        st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
        new_user = st.text_input("Choose Username")
        new_mail = st.text_input("Gmail Address")
        new_pwd = st.text_input("Password", type="password")
        new_role = st.selectbox("Your Role", ["Student", "Teacher", "Researcher", "Professional"])
        if st.button("Create Account", use_container_width=True):
            if new_user and new_mail and new_pwd:
                if add_user(new_user, new_mail, new_pwd, new_role):
                    st.success("Account created! Please login.")
                    st.session_state.auth_mode = "login"
                    st.rerun()
                else:
                    st.error("Username already exists.")
            else:
                st.warning("All fields are required.")
        if st.button("Back to Login", use_container_width=True):
            st.session_state.auth_mode = "login"
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

def main_dashboard():
    with st.sidebar:
        st.markdown('<p class="sidebar-title">Profile</p>', unsafe_allow_html=True)
        st.markdown(f"""<div class="account-box">
            <span class="role-tag">{st.session_state.user_data['role']}</span>
            <p style="margin:5px 0 0 0; font-weight:bold; color:#90EE90; font-size:1.1rem;">{st.session_state.user_data['username']}</p>
            <p style="margin:0; font-size:0.8rem; opacity:0.7;">{st.session_state.user_data['gmail']}</p>
        </div>""", unsafe_allow_html=True)
        st.divider()
        if st.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.analysis_results = None
            st.rerun()

    st.markdown('<h1 class="main-header">PaperIQ</h1>', unsafe_allow_html=True)
    uploaded_file = st.file_uploader("Upload Manuscript", type=["pdf", "docx", "txt"], label_visibility="collapsed")

    if uploaded_file:
        if st.session_state.analysis_results is None or st.button("Re-Analyze"):
            with st.spinner("Extracting intelligence..."):
                raw_sections, full_text = extract_sections_structured(uploaded_file)
                data = analyze_linguistics(full_text)
                keywords = get_frequent_keywords(full_text)
                st.session_state.analysis_results = {
                    "raw_sections": raw_sections,
                    "summaries": {}, 
                    "metrics": data["metrics"],
                    "stats": data["stats"],
                    "issues": data["long_sentences"],
                    "keywords": keywords,
                    "filename": uploaded_file.name,
                    "raw_text": full_text
                }

        res = st.session_state.analysis_results
        
        # Metrics Row
        s_val = res["stats"]["Sentiment"]
        s_label = "Positive / Assertive" if s_val > 0.1 else "Critical / Negative" if s_val < -0.1 else "Neutral / Objective"

        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f'<div class="metric-card"><div class="metric-label">Composite</div><div class="metric-value">{res["metrics"]["Composite"]}</div></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="metric-card"><div class="metric-label">Words</div><div class="metric-value">{res["stats"]["Word Count"]:,}</div></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="metric-card"><div class="metric-label">Sentences</div><div class="metric-value">{res["stats"]["Sentences"]}</div></div>', unsafe_allow_html=True)
        m4.markdown(f'<div class="metric-card"><div class="metric-label">Sentiment</div><div class="metric-value">{s_val}</div><div class="metric-caption">{s_label}</div></div>', unsafe_allow_html=True)

        st.markdown("### 🏷️ Lexical Keywords")
        kw_html = "".join([f'<span class="word-pill">{w} ({c})</span>' for w, c in res["keywords"]])
        st.markdown(f'<div>{kw_html}</div>', unsafe_allow_html=True)
        
        st.divider()

        t1, t2, t3, t4, t5, t6 = st.tabs([
            "📊 Visualisations", 
            "📑 Section Breakdowns", 
            "⚠️ Complexity Alerts",
            "💡 Suggestions", 
            "📝 Detailed Metrics", 
            "❤️ Sentiment"
        ])
        
        with t1:
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("#### Metric Radar")
                cats = list(res["metrics"].keys())[:-1] # Excludes "Composite"
                vals = [res["metrics"][c] for c in cats]
                fig = go.Figure(data=[go.Scatterpolar(r=vals, theta=cats, fill='toself', line_color='#90EE90')])
                fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font_color='white', height=380)
                st.plotly_chart(fig, use_container_width=True)
            with col_b:
                st.markdown("#### Text Statistics")
                fig_bar = go.Figure(data=[
                    go.Bar(name='Avg Sentence Len', x=['Avg Sentence Len'], y=[res['stats']['Avg Sent Len']], marker_color='#0068c9'),
                    go.Bar(name='Avg Word Len', x=['Avg Word Len'], y=[res['stats']['Avg Word Len']], marker_color='#83c9ff')
                ])
                fig_bar.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font_color='white',
                    height=380,
                    margin=dict(t=20, b=20)
                )
                st.plotly_chart(fig_bar, use_container_width=True)
                
            st.markdown("#### Detailed Scores")
            st.markdown(f"""
            <div style="color: #90EE90; padding: 12px; background: rgba(144, 238, 144, 0.05); border-radius: 8px; border: 1px solid rgba(144, 238, 144, 0.2);">
                <div style="display: flex; justify-content: space-around; flex-wrap: wrap;">
                    <p style="margin: 0; line-height: 1.8;"><strong>Language:</strong> {res['metrics']['Language']}/100</p>
                    <p style="margin: 0; line-height: 1.8;"><strong>Coherence:</strong> {res['metrics']['Coherence']}/100</p>
                    <p style="margin: 0; line-height: 1.8;"><strong>Reasoning:</strong> {res['metrics']['Reasoning']}/100</p>
                    <p style="margin: 0; line-height: 1.8;"><strong>Sophistication:</strong> {res['metrics']['Sophistication']}/100</p>
                    <p style="margin: 0; line-height: 1.8;"><strong>Readability:</strong> {res['metrics']['Readability']}/100</p>
                </div>
                <hr style="border-color: rgba(144,238,144,0.2); margin: 8px 0;">
                <p style="text-align: center; margin: 0;"><strong>Overall Tone:</strong> {s_label}</p>
            </div>
            """, unsafe_allow_html=True)

        with t2:
            st.markdown("#### Extracted Section Summaries")
            
            # Key established in initial session state to prevent tab resets. Removed value="Medium".
            summary_length = st.select_slider(
                "Adjust Summary Detail Level:", 
                options=["Short", "Medium", "Long"], 
                key="summary_length_slider" 
            )
            length_map = {"Short": 2, "Medium": 4, "Long": 7}
            num_sentences = length_map.get(summary_length, 4)
            
            # Reset summaries dict to rebuild it dynamically
            res["summaries"] = {}
            
            for title, content in res["raw_sections"].items():
                summary = extractive_summarize(content, num_sentences)
                res["summaries"][title] = summary
                
                with st.expander(f"● {title}"):
                    st.write(summary)

        with t3:
            if res["issues"]:
                st.info("The following sentences may be too complex for general readers:")
                for issue in res["issues"]:
                    st.warning(f"“...{issue[:160]}...”")
            else:
                st.success("Document structure is clear and concise.")
                
        with t4:
            st.subheader("Vocabulary Improvements")
            suggestions_map = {"very": "extremely", "bad": "adverse", "good": "beneficial", "show": "demonstrate", "big": "substantial"}
            text_lower = res['raw_text'].lower()
            found = False
            for s, c in suggestions_map.items():
                if re.search(rf'\b{s}\b', text_lower):
                    st.info(f"Consider replacing **'{s}'** with **'{c}'** for a more academic tone.")
                    found = True
            if not found: st.success("Great vocabulary! No basic academic replacements suggested.")

        with t5:
            d_col1, d_col2 = st.columns(2)
            with d_col1:
                st.write(f"**Total Words:** {res['stats']['Word Count']}")
                st.write(f"**Total Sentences:** {res['stats']['Sentences']}")
            with d_col2:
                st.write(f"**Avg Sentence Length:** {res['stats']['Avg Sent Len']} words")
                st.write(f"**Avg Word Length:** {res['stats']['Avg Word Len']} characters")
                st.write(f"**Sophistication Score:** {res['metrics']['Sophistication']}%")

        with t6:
            st.metric("Sentiment Score", res['stats']['Sentiment'])
            if res['stats']['Sentiment'] > 0.1: 
                st.success("Positive Tone / Assertive")
            elif res['stats']['Sentiment'] < -0.1: 
                st.warning("Critical Tone / Negative")
            else: 
                st.info("Neutral Tone / Objective")

        # Export Section
        st.markdown('<div class="export-section">', unsafe_allow_html=True)
        st.markdown("### 📥 Document Intelligence Report")
        st.markdown("Download a PDF snapshot of the analysis including all linguistic scores.")
        pdf_data = create_pdf_report(res, res["filename"])
        st.download_button("Download Analysis PDF", data=pdf_data, file_name=f"PaperIQ_{res['filename']}.pdf", mime="application/pdf", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.markdown('<p class="sub-header">Upload a paper to begin extraction.</p>', unsafe_allow_html=True)

# -----------------------------
# Entry Point
# -----------------------------
if not st.session_state.logged_in:
    auth_page()
else:
    main_dashboard()