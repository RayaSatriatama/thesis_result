import os
import re

base_dir = '/mnt/nvme0n1p4/Projects/Programming_Projects/thesis_result/scripts/sampling'
files = [
    'expert_judgement_evals_faithfulness_en.md',
    'expert_judgement_evals_faithfulness_id.md',
    'expert_judgement_evals_coherence_en.md',
    'expert_judgement_evals_coherence_id.md'
]

for f in files:
    path = os.path.join(base_dir, f)
    if not os.path.exists(path):
        continue
        
    name = f.replace('expert_judgement_evals_', '').replace('.md', '').upper().replace('_', ' ')
    print(f'\n**{name}:**')
    
    with open(path, 'r', encoding='utf-8') as file:
        content = file.read()
        
    blocks = re.split(r'## Evaluasi Sampel \d+:', content)[1:]
    
    for block in blocks:
        kategori_match = re.search(r'^(.*?)\n', block)
        judul_match = re.search(r'### Judul:\s*(.*?)\n', block)
        coh_match = re.search(r'- \*\*Koherensi.*?:\*\*\s*`([0-9.]+)`', block)
        ragas_match = re.search(r'- \*\*Faithfulness \(RAGAS\):\*\*\s*`([0-9.]+)`', block)
        fables_match = re.search(r'- \*\*Faithfulness \(FABLES\):\*\*\s*`([0-9.]+)`', block)
        
        kategori = kategori_match.group(1).strip() if kategori_match else 'UNKNOWN'
        judul = judul_match.group(1).strip() if judul_match else 'UNKNOWN'
        
        coh = coh_match.group(1) if coh_match else 'N/A'
        ragas = ragas_match.group(1) if ragas_match else 'N/A'
        fables = fables_match.group(1) if fables_match else 'N/A'
        
        kategori = kategori.replace('(Best Cases)', '').replace('(Worst Cases)', '').replace('(Average Case)', '').strip()
        
        print(f'- [{kategori}] {judul} (Coh: {coh}, RAGAS: {ragas}, FABLES: {fables})')
