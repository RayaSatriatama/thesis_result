# Dataset Word Count and Price Estimation

> **Lokasi dalam repositori:** `docs/datasets/dataset_cost_estimation.md` · [Indeks dokumentasi](../index.md)

This document provides a detailed breakdown of unique story word counts across the available datasets and an estimated processing cost using the Gemini 2.5 Flash Lite model for LightRAG ingestion.

## Dataset Statistics

The following statistics represent **unique** stories per dataset (deduplicated by ID or content).

| Dataset | Unique Stories | Total Word Count | Avg Words/Story |
| :--- | :--- | :--- | :--- |
| **NarrativeQA** | 1,572 | 84,098,437 | ~53,497 |
| **WP-STORIES** | 303,155 | 167,694,590 | ~553 |
| **tell_me_a_story** | 123 | 178,194 | ~1,448 |
| **GRAND TOTAL** | **304,850** | **251,971,221** | **~826** |

## Gemini 2.5 Flash Lite Cost Estimation

Estimations are based on a token-to-word multiplier of **1.4** and current Google AI Studio/Vertex AI pricing estimates for Gemini 2.5 Flash Lite.

### 1. Token Metrics

- **Total Words:** 251,971,221
- **Estimated Tokens:** 352,759,709 (~352.7M tokens)

### 2. Pricing Formulas

- **Input Tokens:** $0.10 per 1,000,000 tokens
- **Output Tokens:** $0.40 per 1,000,000 tokens

### 3. LightRAG Processing Estimate

LightRAG ingestion involves reading the input (Input Cost) and extracting entities/relationships (Output Cost). Extraction overhead is estimated at **10%** of the input size.

| Cost Component | Calculation | Estimated Cost |
| :--- | :--- | :--- |
| **Input Cost** | (352.7M / 1M) * $0.10 | $35.2760 |
| **Output Cost (10%)** | (35.27M / 1M) * $0.40 | $14.1104 |
| **TOTAL ESTIMATE** | | **$49.3864** |

> [!NOTE]
> The actual cost may vary based on the specific extraction prompts used by LightRAG and the exact tokenization of the text. This estimate assumes a single pass for graph extraction.

## Dataset Details

### NarrativeQA

Large-scale dataset of long-form stories (books and movie scripts). Characterized by extremely high word counts per document.

### WP-STORIES (WritingPrompts)

Diverse set of shorter stories generated from writing prompts. Comprises the bulk of unique stories in the corpus.

### tell_me_a_story

Curated dataset of short stories, focused on narrative quality.
