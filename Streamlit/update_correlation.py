import re

with open("tabs/correlation.py", "r") as f:
    content = f.read()

# 1. Replace the two old functions with new ones
old_stats_table = re.search(r"def _render_stats_table_section.*?st\.markdown\(\"> \*\*Simpulan Singkat:\*\*.*?\"\)", content, flags=re.DOTALL)
if not old_stats_table:
    print("Could not find the old rendering sections!")
    exit(1)

new_functions = """def _render_main_agentic_section(agentic_df: pd.DataFrame, metrics: list[str]) -> None:
    st.subheader("C. Analisis Utama (Agentic AI, n=100)")
    st.caption("Analisis korelasi utama dilakukan terhadap 100 trace sistem agentic AI karena variabel jumlah revisi hanya terdapat pada sistem tersebut. Data kedua sistem tidak langsung digabungkan dalam analisis utama karena perbedaan karakteristik sistem dan rata-rata skor dapat memengaruhi pola korelasi yang diperoleh (Simpson's paradox).")
    
    if agentic_df is None or agentic_df.empty:
        st.info("Data Agentic AI tidak tersedia.")
        return
        
    core_avail = [m for m in CORE_METRICS if m in metrics]
    
    import ast
    def clean_rc(x):
        try:
            if isinstance(x, str) and x.startswith("["):
                return float(ast.literal_eval(x)[0])
            return float(x)
        except:
            return None
            
    df_clean = agentic_df.copy()
    if "revision_count" in df_clean.columns:
        df_clean["revision_count"] = df_clean["revision_count"].apply(clean_rc)
        
    rows = []
    
    # 1. Faithfulness and Coherence pairwise
    pairwise = _compute_pairwise_stats(df_clean, core_avail)
    for p in pairwise:
        rows.append({
            "Pasangan metrik": f"{p['Metrik A']} vs {p['Metrik B']}",
            "ρ ≈ 0": f"{p['Spearman rho']:.3f}",
            "p-value": "< 0.001" if p['Spearman p'] < 0.001 else f"{p['Spearman p']:.3f}",
            "Interpretasi": _interpret_correlation(p['Spearman rho'], p['Spearman p']),
            "_rho": p['Spearman rho']
        })
        
    # 2. Revision count pairwise
    if "revision_count" in df_clean.columns:
        for m in core_avail:
            valid = df_clean[["revision_count", m]].dropna()
            if len(valid) < 5: continue
            rho, p_val = scipy_stats.spearmanr(valid["revision_count"], valid[m])
            rows.append({
                "Pasangan metrik": f"{METRIC_DISPLAY.get(m, m)} vs revisi",
                "ρ ≈ 0": f"{rho:.3f}",
                "p-value": "< 0.001" if p_val < 0.001 else f"{p_val:.3f}",
                "Interpretasi": _interpret_correlation(rho, p_val),
                "_rho": float(rho)
            })
            
    if not rows:
        st.info("Tidak cukup data untuk menghitung korelasi statistik Agentic AI.")
        return
        
    res_df = pd.DataFrame(rows)
    display_df = res_df.drop(columns=["_rho"])
    
    def _row_style(row: pd.Series):
        rho = res_df.iloc[row.name]["_rho"]
        if abs(rho) >= 0.5:
            return ["background-color: rgba(34, 197, 94, 0.1)"] * len(row)
        if abs(rho) >= 0.3:
            return ["background-color: rgba(234, 179, 8, 0.1)"] * len(row)
        return ["background-color: rgba(239, 68, 68, 0.08)"] * len(row)

    st.dataframe(
        display_df.style.apply(_row_style, axis=1),
        use_container_width=True,
        hide_index=True,
    )
    st.markdown("> **Simpulan Singkat:**\\n> Korelasi pada 100 trace agentic AI menjelaskan hubungan antarmetrik dan dinamika revisi di dalam arsitektur multiagen. *Faithfulness* dan koherensi tidak saling bergantung secara signifikan. Jumlah revisi berkolerasi negatif dengan skor akhir, menunjukkan bahwa sistem melakukan lebih banyak intervensi revisi untuk cerita yang pada dasarnya sudah kompleks/problematik sejak awal.")


def _render_additional_baseline_section(baseline_df: pd.DataFrame, metrics: list[str]) -> None:
    st.subheader("D. Analisis Tambahan (Baseline, n=100)")
    st.caption("Korelasi antara faithfulness dan koherensi naratif dianalisis secara terpisah pada 100 trace baseline sebagai analisis pembanding untuk melihat apakah pola hubungan metrik berbeda antara sistem generasi alur tunggal dan sistem agentic AI.")
    
    if baseline_df is None or baseline_df.empty:
        st.info("Data Baseline tidak tersedia.")
        return
        
    core_avail = [m for m in CORE_METRICS if m in metrics]
    pairwise = _compute_pairwise_stats(baseline_df, core_avail)
    
    if not pairwise:
        st.info("Tidak cukup data untuk menghitung korelasi statistik Baseline.")
        return
        
    rows = []
    for p in pairwise:
        rows.append({
            "Pasangan metrik": f"{p['Metrik A']} vs {p['Metrik B']}",
            "ρ ≈ 0": f"{p['Spearman rho']:.3f}",
            "p-value": "< 0.001" if p['Spearman p'] < 0.001 else f"{p['Spearman p']:.3f}",
            "Interpretasi": _interpret_correlation(p['Spearman rho'], p['Spearman p']),
            "_rho": p['Spearman rho']
        })
        
    res_df = pd.DataFrame(rows)
    display_df = res_df.drop(columns=["_rho"])
    
    def _row_style(row: pd.Series):
        rho = res_df.iloc[row.name]["_rho"]
        if abs(rho) >= 0.5:
            return ["background-color: rgba(34, 197, 94, 0.1)"] * len(row)
        if abs(rho) >= 0.3:
            return ["background-color: rgba(234, 179, 8, 0.1)"] * len(row)
        return ["background-color: rgba(239, 68, 68, 0.08)"] * len(row)

    st.dataframe(
        display_df.style.apply(_row_style, axis=1),
        use_container_width=True,
        hide_index=True,
    )
"""

content = content[:old_stats_table.start()] + new_functions + content[old_stats_table.end():]

# 2. Update the calls in render_correlation_tab
call_pattern = r"_render_stats_table_section\(combined, metrics\)\n\s+st\.divider\(\)\n\s+_render_revision_section\(combined, metrics\)"
new_calls = "_render_main_agentic_section(current_lang, metrics)\n    st.divider()\n\n    _render_additional_baseline_section(baseline_lang, metrics)"

content = re.sub(call_pattern, new_calls, content)

with open("tabs/correlation.py", "w") as f:
    f.write(content)
print("Done rewriting")
