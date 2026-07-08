import streamlit as st
import sys
import os

# Add scripts/sampling to path globally so that cached functions can resolve sampling_expert
_sampling_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "sampling"))
if _sampling_path not in sys.path:
    sys.path.insert(0, _sampling_path)

from tabs.architecture import render_architecture_tab
from tabs.coherence import render_coherence_tab
from tabs.faithfulness import render_faithfulness_tab
from tabs.correlation import render_correlation_tab
from tabs.lightrag import render_lightrag_sidebar, render_lightrag_tab
from tabs.wikieval import render_wikieval_tab

st.set_page_config(
    page_title="Evaluasi Agentic AI — Faithfulness, Koherensi & Arsitektur",
    layout="wide",
    page_icon="🏆",
)

st.title("🏆 Evaluasi Agentic AI — Faithfulness, Koherensi & Arsitektur")
st.markdown(
    "Dashboard analisis eksperimen **Agentic AI** berbasis LangGraph untuk pembuatan cerita edukatif. "
    "Mencakup arsitektur pipeline, evaluasi **Faithfulness** (FABLES/RAGAS), "
    "**Koherensi Naratif** (G-Eval/EHM), EDA dataset **WikiEval**, dan perbandingan penyimpanan **LightRAG**."
)

with st.sidebar:
    baseline_root, custom_before = render_lightrag_sidebar()

custom_root = custom_before.strip() or None

tab_arch, tab_faith, tab_coh, tab_corr, tab_wiki, tab_lightrag = st.tabs([
    "Arsitektur Agentic AI",
    "Faithfulness",
    "Coherence",
    "Korelasi Metrik",
    "WikiEval",
    "Analisis LightRAG",
])

with tab_arch:
    render_architecture_tab()

with tab_faith:
    try:
        render_faithfulness_tab()
    except Exception as e:
        st.error(f"Error rendering Faithfulness tab: {e}")
        st.exception(e)

with tab_coh:
    render_coherence_tab()

with tab_corr:
    render_correlation_tab()

with tab_wiki:
    render_wikieval_tab()

with tab_lightrag:
    render_lightrag_tab(baseline_root, custom_root)
