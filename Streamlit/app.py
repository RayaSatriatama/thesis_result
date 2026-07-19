import streamlit as st

from tabs.architecture import render_architecture_tab
from tabs.coherence import render_coherence_tab
from tabs.faithfulness import render_faithfulness_tab
from tabs.correlation import render_correlation_tab
from tabs.lightrag import render_lightrag_sidebar, render_lightrag_tab
from tabs.wikieval import render_wikieval_tab
from tabs.sampling import render_sampling_tab

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

tab_arch, tab_faith, tab_coh, tab_corr, tab_wiki, tab_lightrag, tab_samp = st.tabs([
    "Arsitektur Agentic AI",
    "Faithfulness",
    "Coherence",
    "Korelasi Metrik",
    "WikiEval",
    "Analisis LightRAG",
    "Expert Sampling",
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

with tab_samp:
    render_sampling_tab()
