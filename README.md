# PromptGate

PE6201 individual project by Siwen Liu. PromptGate is a small safety gateway placed before an enterprise RAG assistant. It screens one English input and returns a fixed `Allow`, `Block`, or `Review` decision, a score, and a reason. A downstream RAG system and tool execution are outside this prototype.

The design follows the August Problem Statement and the instructor's September feedback:

- the classifier owns the decision;
- a language model may explain a `Review` case only;
- the explanation endpoint is unreachable for `Allow` and `Block`, and its response cannot change the action;
- thresholds are selected on a development split;
- the external 662-row deepset set is evaluation-only;
- the original S-Labs training CSV is used for the teacher-requested 11,089-row training run.

## Quick start

Python 3.9+ is supported. The included frozen model artifacts let the local console run without downloading datasets.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[ml,app]'
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m promptgate.webapp
```

Open `http://127.0.0.1:8765/`. The console makes no network call for `/screen`; an OpenRouter key is required only if a reviewer explicitly asks for an explanation of a `Review` case. The key is accepted for one request in memory and is never written to a file.

The default model is the frozen Naive Bayes model trained on the original 11,089 S-Labs rows. The second option is a word-and-character logistic regression model. Both use the same frozen source-domain policy procedure.

## Reproduce the data and model

The raw files are intentionally outside this repository. Put these public downloads in `../research/topic_selection/data/`:

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
  --source ../research/topic_selection/data \
  --output data/processed/v1

.venv/bin/python -m promptgate.ml train \
  --data data/processed/v1 \
  --raw-train ../research/topic_selection/data/prompt_injection_train.csv \
  --models models/teacher-11089

.venv/bin/python -m promptgate.ml benchmark \
  --data data/processed/v1 \
  --models models/teacher-11089 \
  --output results/runs/teacher-11089-external-01
```

`prepare` checks source row counts, hashes, labels, normalized duplicates, conflicts, and overlap. The four duplicated validation texts that also occur in the original training CSV are removed from calibration/policy selection; the training rows are preserved. The threshold and review margin are selected only on the remaining validation data. No external label is read until the model, threshold, and selected candidate are frozen.

The deepset metadata contains inconsistent license labels. It is therefore used only for local evaluation and is not redistributed in this repository. Public datasets were explored during the proposal stage, so this is a frozen prospective evaluation, not a claim of never-seen data.

## Measured results

The submitted evidence is in `evidence/teacher-11089-summary.json`; the full local run is `results/runs/teacher-11089-external-20260925-01/summary.json`. The selected candidate is Naive Bayes because it had the highest policy-split attack recall while meeting the 5% development FPR cap. The external FPR is reported exactly as observed.

| Frozen policy | Data | Attack block recall | Benign block FPR | Review rate | Confusion (TP/FP/FN/TN) |
|---|---:|---:|---:|---:|---|
| Naive Bayes | development policy, n=991 | 99.6% | 4.0% | 0.0% | 469/21/2/499 |
| Naive Bayes | S-Labs remaining test, n=2,001 | 95.6% | 4.8% | 0.0% | — |
| Naive Bayes | external deepset original, n=662 | 79.8% | **43.1%** | 0.0% | **210/172/53/227** |
| Logistic word+character | external deepset original, n=662 | 69.2% | 16.0% | 0.0% | — |
| Hybrid selected Naive Bayes + Review | external deepset original, n=662 | 76.4% | 36.8% | 27.9% | — |

The external result does not meet the 5% FPR aspiration. It demonstrates domain shift: a threshold that is safe on the S-Labs development distribution is not safe on this external set. This is the main business/technical trade-off in the project and is kept visible in the UI and report.

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

The project applies Class 1 rule baselines and narrow ML, Class 2 build/buy and evaluation choices, Class 3 structured outputs and local contract validation, Class 5 measured latency/token/cost accounting, and Class 6 executable guardrails and regression tests. The final submission package consists of the August Problem Statement, this repository, the recorded demo, and `TRADEOFF_REPORT.md`; the current course timeline gives 4 October 2026, 23:59 SGT and caps the trade-off report at 1,200 words.
