import json
import glob
import os

base_dir = '/mnt/nvme0n1p4/Projects/Programming_Projects/thesis_result'
obs_path = os.path.join(base_dir, 'Eval_Data', 'Observations', '*.jsonl')
files = glob.glob(obs_path)
latest_obs = max(files, key=os.path.getmtime)

claims_per_trace = {}
with open(latest_obs, 'r', encoding='utf-8') as f:
    for line in f:
        if not line.strip(): continue
        try:
            data = json.loads(line)
            if data.get('name') == 'fables_verify_all_claims':
                trace_id = data.get('traceId')
                output = data.get('output', {})
                if isinstance(output, str):
                    try:
                        output = json.loads(output)
                    except:
                        pass
                if isinstance(output, dict) and 'verdicts' in output:
                    claims = output.get('verdicts', [])
                    claims_per_trace[trace_id] = len(claims)
        except Exception as e:
            pass

print(f"Total traces with FABLES claims: {len(claims_per_trace)}")

import pandas as pd
df = pd.read_csv(max(glob.glob(os.path.join(base_dir, 'Eval_Data', 'Traces', '*.csv')), key=os.path.getmtime))
df['id'] = df['id'].astype(str).str.strip('"')

# Re-run the stratification logic for coherence
# Let's see if coherence sampling produces 117 claims
from scripts.sampling.sampling_expert import parse_metric

df['geval_coherence_normalized'] = df.get('geval_coherence_normalized', pd.Series(dtype=float)).apply(parse_metric)
df['ragas_standard_faithfulness'] = df.get('ragas_standard_faithfulness', pd.Series(dtype=float)).apply(parse_metric)
df['fables_faithfulness'] = df.get('fables_faithfulness', pd.Series(dtype=float)).apply(parse_metric)

def get_sampled_ids(df, prompt_filter, priority):
    d = df[df['input'].astype(str).str.contains(prompt_filter, na=False)].copy()
    d = d.dropna(subset=['geval_coherence_normalized', 'ragas_standard_faithfulness', 'fables_faithfulness']).copy()
    
    if priority == 'faithfulness':
        d['faithfulness_avg'] = (d['ragas_standard_faithfulness'] + d['fables_faithfulness']) / 2.0
        sort_metrics = ['faithfulness_avg', 'geval_coherence_normalized']
        asc_high = [False, False]
        asc_low = [True, True]
    else:
        sort_metrics = ['geval_coherence_normalized', 'ragas_standard_faithfulness', 'fables_faithfulness']
        asc_high = [False, False, False]
        asc_low = [True, True, True]

    t = d.sort_values(by=sort_metrics, ascending=asc_high).head(2)
    d = d.drop(t.index)
    r = d.sort_values(by=sort_metrics, ascending=asc_low).head(2)
    d = d.drop(r.index)
    
    med_c = d['geval_coherence_normalized'].median()
    med_r = d['ragas_standard_faithfulness'].median()
    med_f = d['fables_faithfulness'].median()
    d['dist'] = ((d['geval_coherence_normalized'] - med_c)**2 + (d['ragas_standard_faithfulness'] - med_r)**2 + (d['fables_faithfulness'] - med_f)**2)**0.5
    s = d.sort_values('dist').head(1)
    
    return t['id'].tolist() + r['id'].tolist() + s['id'].tolist()

en_coh = get_sampled_ids(df, "Create an", "coherence")
id_coh = get_sampled_ids(df, "Buat cerita", "coherence")
coh_ids = en_coh + id_coh
claims_coh = sum(claims_per_trace.get(tid, 0) for tid in coh_ids)
print(f"Total claims in Coherence samples: {claims_coh}")

en_fai = get_sampled_ids(df, "Create an", "faithfulness")
id_fai = get_sampled_ids(df, "Buat cerita", "faithfulness")
fai_ids = en_fai + id_fai
claims_fai = sum(claims_per_trace.get(tid, 0) for tid in fai_ids)
print(f"Total claims in Faithfulness samples: {claims_fai}")
