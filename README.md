# PromptGate

PE6201 individual project by SIwen Liu. PromptGate is a small safety gateway placed before an enterprise RAG assistant. It screens one English input and returns a fixed `Allow`, `Block`, or `Review` decision, a score, and a reason. A downstream RAG system and tool execution are outside this prototype.

The design follows the August Problem Statement and the instructor's September feedback:

- the classifier owns the decision;
- a language model may explain a `Review` case only;
- the explanation endpoint is unreachable for `Allow` and `Block`, and its response cannot change the action;
- thresholds are selected on a development split;
- the external 662-row deepset set is evaluation-only;
- the original S-Labs training CSV is used for the teacher-requested 11,089-row training run.

## Reviewer guide

- [Product documentation and architecture](docs/PRODUCT.md): persona, input/output, exact routing, targets and reached metrics.
- [Data explanation](data_sources/README.md): checked-in S-Labs snapshots, split construction, licences and external-data acquisition.
- [Evaluation explanation](evals/README.md): metric definitions, full prediction records, limitations and reproduction.
- [Module guide](docs/MODULES.md): responsibilities and boundaries at file level.
- [Trade-off report](TRADEOFF_REPORT.md) and [face-plus-screen demo script](DEMO_SCRIPT.md).

## Quick start

Python 3.11+ is required for the ML and web-app extras. The included frozen model artifacts let the local console run without downloading datasets.

```sh
python3.11 -m venv .venv  # or any installed Python 3.11+ interpreter
.venv/bin/python -m pip install -e '.[ml,app]'
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/verify_evidence.py
.venv/bin/python -m promptgate.webapp
```

Open `http://127.0.0.1:8765/`. The console makes no network call for `/screen`; an OpenRouter key is required only if a reviewer explicitly asks for an explanation of a `Review` case. The key is accepted for one request in memory and is never written to a file.

The tested environment uses Python 3.12.14; exact dependency versions are recorded in `requirements-tested.txt`. To match it, use `.venv/bin/python -m pip install -r requirements-tested.txt` followed by `.venv/bin/python -m pip install -e .`. The report authoring helper optionally requires `python-docx`; it is not part of the app runtime. Submitted report exports are under `output/docx/` and `output/pdf/`.

The default model is the frozen Naive Bayes model trained on the original 11,089 S-Labs rows. The second option is a word-and-character logistic regression model. The web console applies the hybrid policy: a high score blocks, a near-boundary score goes to Review, and only a low score is allowed. The binary classifier-only numbers below are reported separately from the web application's hybrid numbers.

## Reproduce the data and model

The console and offline evidence verifier work with the included files. The original S-Labs source files are checked in under `data_sources/slabs/`; the deepset raw text is not redistributed. For a complete local rerun, first review the source terms in [the data explanation](data_sources/README.md), then fetch the pinned external inputs into Git-ignored `data/raw/`:

```sh
.venv/bin/python -m pip install -e '.[ml,app,data]'
.venv/bin/python scripts/fetch_external.py --accept-source-terms
```

This produces the following verified local source files:

```text
prompt_injection_train.csv                 11,089 rows
prompt_injection_validation.csv             2,101 rows
prompt_injection_test.csv                   2,101 rows
deepset_prompt_injection_train.parquet        546 rows
deepset_prompt_injection_test.parquet         116 rows
```

Then run:

```sh
.venv/bin/python -m promptgate prepare \
  --source data/raw \
  --output data/processed/reproduction

.venv/bin/python -m promptgate.ml train \
  --data data/processed/reproduction \
  --raw-train data/raw/prompt_injection_train.csv \
  --models models/reproduction

.venv/bin/python -m promptgate.ml benchmark \
  --data data/processed/reproduction \
  --models models/reproduction \
  --output results/runs/reproduction
```

`prepare` checks source row counts, hashes, labels, normalized duplicates, conflicts, and overlap. It removes 116 validation texts overlapping the test split. Training with the original CSV then excludes another four validation texts that overlap training, leaving 990 calibration and 991 policy rows. The original training rows are preserved, including duplicates and label conflicts. Only development data determines the threshold, review margin and selected candidate. Preprocessing reads external labels for integrity checks, but external evaluation scores are not used for fitting or selection. Use fresh output directory names for each rerun: existing evidence is never overwritten.

The deepset metadata contains inconsistent license labels. It is therefore used only for local evaluation and is not redistributed in this repository. Public datasets were explored during the proposal stage, so this is a frozen prospective evaluation, not a claim of never-seen data.

## Measured results

The headline evidence is in `evidence/teacher-11089-summary.json`; the complete checked-in summary and eight text-free prediction files are in `evidence/offline/`. The selected candidate is Naive Bayes because it had the highest policy-split attack recall while meeting the 5% development FPR cap. The web application uses its frozen hybrid Review policy; the classifier-only row is a paired comparison. External FPR is reported exactly as observed.

| Frozen policy | Data | Attack block recall | Benign block FPR | Review rate | Confusion (TP/FP/FN/TN) |
|---|---:|---:|---:|---:|---|
| Naive Bayes | development policy, n=991 | 99.6% | 4.0% | 0.0% | 469/21/2/499 |
| Naive Bayes | S-Labs remaining test, n=2,001 | 95.6% | 4.8% | 0.0% | — |
| Naive Bayes | external deepset original, n=662 | 79.8% | **43.1%** | 0.0% | **210/172/53/227** |
| Logistic word+character | external deepset original, n=662 | 69.2% | 16.0% | 0.0% | — |
| **Hybrid selected Naive Bayes + Review (web app)** | external deepset original, n=662 | **76.4%** | **36.8%** | **27.9%** | 201/147/62/252 |

The final target is at least 80% external attack recall and at most 5% benign block FPR. It is not met. For the web application's hybrid policy, Review captured 53 of 225 counterfactual binary errors (23.6%) before abstention; no human-correction accuracy was measured. Including Review, 295/399 benign inputs were held (73.9%), while 25/263 attacks were allowed. The gap is consistent with distribution shift, but the experiment does not isolate its cause. A development threshold is not a safety guarantee. This is the central business/technical trade-off.

The separate 100-row live GPT-4o-mini MVP run made 100 real OpenRouter calls with no technical failures. It blocked 25/50 attacks (50.0% recall), blocked 0/50 benign prompts (0% FPR), sent 13% to Review, had p95 latency 3.42 seconds, and cost US$0.0066129 according to provider usage. It did not meet the historical 58.3% MVP target. That 58.3% value is a cited reference, not this project's result.

## What is implemented

- `promptgate/ml.py`: TF-IDF Naive Bayes and word/character logistic regression, sigmoid calibration, development-only threshold selection, Review routing, checksum-verified model loading, and offline benchmarking.
- `promptgate/baselines.py`: deterministic rule baseline.
- `promptgate/llm.py`: one-call structured-output MVP with local validation and fail-closed `Review` handling.
- `promptgate/explanation.py`: optional Review-only explanation call; the model returns a reason, never an action.
- `promptgate/webapp.py` and `promptgate/static/index.html`: local FastAPI review console.
- `tests/`: contract, leakage, metric, model-policy, API-boundary, and no-network regression tests.

Run the tests from this directory:

```sh
.venv/bin/python -m unittest discover -s tests -v
```

## Scope and risks

The prototype screens a standalone input. It does not inspect retrieved documents, multi-turn state, model outputs, tools, or user identity. A high score is a model signal, not a verified fact. False positives create review workload; false negatives can reach the downstream assistant. Provider logging and retention policies are outside local control. The next production step would be a new organization-specific labelled set, threshold re-selection with an agreed operational FPR, drift monitoring, and a human approval queue.

## Course mapping and deliverables

The project applies Class 1 rule baselines and narrow ML, Class 2 build/buy and evaluation choices, Class 3 structured outputs and local contract validation, Class 5 measured latency/token/cost accounting, and Class 6 executable guardrails and regression tests. Class 4 autonomous agents are deliberately omitted because bounded screening needs no autonomous tool loop.

The repository includes the trade-off report, product architecture, data and evaluation explainers, frozen models, prediction records and module documentation. The original Problem Statement and recorded face-plus-screen demo accompany the course submission separately. If the repository is private, the marker needs access or the complete code ZIP. The deepset raw-text exception remains subject to the instructor's confirmation; acquisition instructions and text-free evidence are included.
