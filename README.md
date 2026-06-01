# Whitepaper Credibility Checker

Research project for extracting signals from cryptocurrency whitepapers and using them for downstream credibility assessment. The repository contains the application and pipeline code used for the thesis implementation, while large research assets such as whitepapers, annotations, experiment outputs, and model checkpoints are kept out of GitHub.

## What this repo contains

- A Flask backend for whitepaper analysis APIs
- A React + Vite frontend for the checker UI
- A Python NLP pipeline for preprocessing, section classification, and downstream analysis
- Tests and utility scripts for local development

## Excluded assets

This GitHub repository intentionally excludes several local-only assets:

- source whitepaper PDFs
- extracted and annotated datasets
- fine-tuning outputs and experiment artifacts
- trained checkpoints under `models/`
- local virtual environments and caches

That keeps the repository lighter and avoids redistributing third-party material directly from GitHub.

## Final model checkpoint

The application's fine-tuned section classifier currently expects the final checkpoint at:

```text
models/roberta-finetuned-v6-aug
```

The default path is referenced by the section-classifier runtime, so after uploading the model to Hugging Face, download it back into that local directory before running fine-tuned inference.

Example using `huggingface_hub`:

```bash
pip install huggingface_hub
python -c "from huggingface_hub import snapshot_download; snapshot_download(repo_id='cygnuscygnus/wp-section-classifier-RoBERTa', local_dir='models/roberta-finetuned-v6-aug', local_dir_use_symlinks=False)"
```

Hugging Face model repository:

`https://huggingface.co/cygnuscygnus/wp-section-classifier-RoBERTa`

## Local setup

### 1. Python environment

Create and activate a virtual environment, then install the backend and ML dependencies used by the current app and pipeline:

```bash
pip install -r backend/requirements.txt
pip install torch transformers sentence-transformers spacy nltk scikit-learn pdfminer.six
python -m spacy download en_core_web_sm
python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords'); nltk.download('wordnet')"
```

Note: `backend/requirements.txt` only covers the Flask service layer. The ML pipeline also needs the additional NLP packages above.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

The Vite development server runs on `http://localhost:5173` by default.

### 3. Backend

From the project root:

```bash
python backend/app.py --debug
```

The backend runs on `http://localhost:5000` by default.

Health check:

```text
GET /api/health
```

### 4. Optional local services

- MongoDB default URI: `mongodb://localhost:27017/`
- MongoDB default database: `skripsi_wp`

These defaults are configured in the Flask app and can be overridden in code or startup config.

## Running the pipeline

The batch pipeline supports fine-tuned section classification through `pipeline/batch_runner.py`. The fine-tuned path requires the v6 checkpoint to be present locally under `models/roberta-finetuned-v6-aug`.

Typical local command:

```bash
python pipeline/batch_runner.py
```

## Notes for publication

- This repository is the code-facing part of the thesis project.
- Large research artifacts are intentionally excluded from version control.
- Model checkpoint: `https://huggingface.co/cygnuscygnus/wp-section-classifier-RoBERTa`
