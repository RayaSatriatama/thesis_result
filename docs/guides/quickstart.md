# Quick Start Guide

## 📋 Prerequisites Checklist

- [ ] Python 3.9+ installed
- [ ] Git installed
- [ ] OpenAI API key (atau Google Gemini API key)
- [ ] Minimum 8GB RAM
- [ ] Minimum 10GB disk space

## 🚀 Setup (5 menit)

### 1. Clone & Navigate

```bash
cd D:\Projects\Programming_Projects\Skripsi
```

### 2. Setup Environment

```bash
# Jalankan setup script
python scripts/setup_environment.py

# Atau manual:
python -m venv venv
.\venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 3. Configure API Keys

```bash
# Copy template
cp .env.example .env

# Edit .env file
# Tambahkan your API keys:
OPENAI_API_KEY=sk-your-key-here
GOOGLE_API_KEY=your-gemini-key-here
```

## 🏃 Running the API Server

Start the backend server to access the Story Generation API.

```bash
# Default (Text generation only)
python -m src.apps.api.main

# With Image Generation (requires ImageKit)
$env:ENABLE_IMAGE_WRITER="true"; python -m src.apps.api.main
```

The API will be available at `http://localhost:8000`.

- **Docs**: [Story Generation API](../api/story_generation.md)

## 📊 Dataset Preparation

### Option 1: Download HANNA Dataset

```bash
python scripts/download_dataset.py
```

### Option 2: Use Custom Story Corpus

```bash
# Place your stories in:
data/raw/story_corpus/

# Build Knowledge Graph:
python scripts/build_kg.py --corpus data/raw/story_corpus
```

## 🧪 Run Your First Experiment

### Quick Test

```python
# test_basic.py
import asyncio
from src.agentic_ai import StateTracker, EpisodicSummarizer

async def main():
    # Test State Tracker
    tracker = StateTracker()
    tracker.track_item("magic_sword")
    change = tracker.update_state("magic_sword", ItemState.LOST)
    print(f"State changed: {change.is_valid}")
    
    # Test Summarizer
    summarizer = EpisodicSummarizer()
    summary = await summarizer.summarize_episode(
        "Alice found a magic sword in the ancient ruins."
    )
    print(f"Episode summarized: {summary.episode_id}")

asyncio.run(main())
```

### Full Experiment

```bash
# Run dengan default config
python scripts/run_experiment.py

# Run dengan custom settings
python scripts/run_experiment.py \
    --config config/experiment_config.yaml \
    --model gpt-4o-mini \
    --output data/results/exp_001
```

## 📈 Analysis

### Jupyter Notebooks

```bash
# Start Jupyter
jupyter notebook

# Open notebooks:
notebooks/01_data_exploration.ipynb
notebooks/02_kg_construction.ipynb
notebooks/03_evaluation_analysis.ipynb
notebooks/04_visualization.ipynb
```

### Quick Stats

```python
import pandas as pd

# Load results
results = pd.read_csv('data/results/experiment_001/metrics.csv')

# Basic stats
print(results.describe())
print(f"Coherence: {results['coherence'].mean():.3f}")
print(f"Faithfulness: {results['faithfulness'].mean():.3f}")
```

## 🔧 Common Tasks

### Build Knowledge Graph

```bash
python scripts/build_kg.py \
    --corpus data/raw/story_corpus \
    --output data/processed/knowledge_graph
```

### Evaluate Generated Stories

```bash
python -m src.evaluation.evaluate \
    --stories data/results/generated_stories.json \
    --kg data/processed/knowledge_graph \
    --output data/results/evaluation.json
```

### Export Results

```bash
python -m src.utils.export_results \
    --input data/results/experiment_001 \
    --format excel \
    --output results_summary.xlsx
```

## 🐛 Troubleshooting

### Issue: Import Errors

```bash
# Make sure src is in PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"  # Linux/Mac
$env:PYTHONPATH = "${PWD}/src"  # PowerShell
```

### Issue: LightRAG Storage Errors

```bash
# Clear storage
rm -rf data/processed/lightrag_storage
mkdir -p data/processed/lightrag_storage
```

### Issue: Out of Memory

```python
# Reduce batch size in config
# Edit config/experiment_config.yaml:
retrieval:
  top_k: 30  # Reduce from 60
  chunk_top_k: 3  # Reduce from 5
```

## 📚 Documentation

- **Architecture**: `docs/architecture.md`
- **LightRAG**: `docs/LIGHTRAG_DOCUMENTATION.md`
- **API Reference**: `docs/api_reference.md` (to be created)
- **Paper**: `Proposal.md`

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# Run specific test
pytest tests/test_state_tracker.py

# With coverage
pytest --cov=src tests/
```

## 📊 Expected Results

After running baseline experiment, you should see:

```
Experiment: baseline
Dataset: HANNA (test split)
Stories generated: 50

Metrics:
- Coherence Score: 0.823 ± 0.045
- Faithfulness Score: 0.912 ± 0.031
- Consistency Score: 0.887 ± 0.052
- EASM Score: 0.856 ± 0.048

Continuity Errors: 3 (5.9% of stories)
Hallucinations: 2 (3.9% of stories)
```

## 🔄 Typical Workflow

```
1. Setup environment ✓
2. Configure .env ✓
3. Download/prepare dataset ✓
4. Build Knowledge Graph ✓
5. Run baseline experiment
6. Analyze results
7. Iterate dengan different configs
8. Compare ablation studies
9. Generate visualizations
10. Write research paper
```

## 💡 Tips

1. **Start Small**: Test dengan 5-10 stories first
2. **Use Logging**: Check `logs/` untuk debugging
3. **Save Configs**: Always save experiment configs
4. **Version Control**: Commit setelah each major change
5. **Monitor Costs**: Track API usage untuk OpenAI/Gemini

## 🆘 Need Help?

- Check existing issues: [GitHub Issues]
- Email: <your-email@student.upi.edu>
- Documentation: `docs/`
- Code comments: All modules have docstrings

## 📝 Citation

Jika menggunakan code ini dalam research:

```bibtex
@mastersthesis{satriatama2025agentic,
  title={Analisis Kinerja Koherensi Naratif dan Faithfulness pada Sistem Agentic AI dan LightRAG untuk Pembelajaran Berbasis Cerita},
  author={Satriatama, Mohammad Raya},
  year={2025},
  school={Universitas Pendidikan Indonesia}
}
```

---

**Last Updated**: November 2025
**Status**: ✅ Ready for Research
