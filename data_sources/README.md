# Data explanation and provenance

## Sources and labels

| Source | Original rows | Labels | Project use |
| --- | ---: | --- | --- |
| [S-Labs prompt-injection-dataset](https://huggingface.co/datasets/S-Labs/prompt-injection-dataset) | Train 11,089; validation 2,101; test 2,101 | 0 benign, 1 injection | Training, calibration, policy selection and same-source holdout |
| [deepset prompt-injections](https://huggingface.co/datasets/deepset/prompt-injections) | Train 546; test 116; total 662 | 0 benign, 1 injection | External evaluation only; both upstream splits form one benchmark |

These are text classification labels, not observed successful attacks against a running RAG assistant. Treat dataset prompts as inert, untrusted text, never instructions to execute. No organisation-specific data, live user PII or consented user study was collected. English is the intended product scope; the external benchmark is kept in its original composition, not filtered to support a claim of English-only evaluation.

## Included files and licence boundary

`slabs/` includes exact copies of the three original S-Labs CSV files used in the experiment, plus the upstream dataset card. The publisher marks the dataset MIT. Attribution and terms are in [NOTICE.md](NOTICE.md). `processed/` includes the four S-Labs JSONL subsets used by the project: cleaned train, prepared validation, the fixed 100-row MVP and remaining test. The teacher-requested model uses the **original** train CSV, not the cleaned train subset.

`preparation_manifest.json` preserves input/output SHA-256 hashes, label counts, removed rows, overlap counts and MVP IDs. `source_manifest.json` maps the original files to pinned upstream locations and the recorded checksums. Upstream bytes must match before reuse; a changed download must not silently replace a frozen input.

The deepset card has top-level `apache-2.0` and nested `cc-by-4.0` metadata, rechecked on 2 October 2026. In line with the proposal and instructor feedback, no deepset prompt text is redistributed. Text-free prediction records contain row IDs, ground-truth labels and hashes so metrics can be audited without the prompts. Fetch the two source files locally only after reviewing the source terms; see the optional command below. Teacher acceptance of source links plus hashes instead of the external raw text is a submission clarification still to confirm, not an assumed waiver of the latest data requirement.

## Split construction

1. Normalise text using Unicode casefold and whitespace collapse for duplicate detection. Original input text is not replaced by that normalisation for modelling.
2. Preserve external evaluation and S-Labs test rows ahead of development rows. Remove 116 validation texts overlapping the S-Labs test, leaving 1,985 prepared validation rows.
3. For the instructor-requested original 11,089-row training run, remove another four validation texts overlapping that original train file. Split the remaining 1,981 rows into 990 sigmoid-calibration rows and 991 policy-selection rows with stratification and seed 6201.
4. Preserve all original training rows in that run, including 39 normalised duplicate rows and one text with conflicting labels. The separate cleaned 11,045-row train file is not the source of the reported model.
5. Select 50 benign and 50 injection S-Labs test rows with seed 6201 for the fixed MVP. The remaining 2,001 test rows contain 1,001 injections and 1,000 benign inputs.
6. Keep all 662 deepset rows: 263 injections and 399 benign inputs. Cleaned and original external files have identical hashes; they are **one** benchmark, not two independent tests.

No exact normalised text overlap was found between original S-Labs train and deepset in the recorded audit. This does not rule out semantic overlap or benchmark familiarity. Public datasets were explored during proposal work. Preprocessing inspects labels for conflict auditing; external scores were not used for fitting, calibration, policy or model selection in the frozen run.

## Reproduction

The included S-Labs files, models and prediction records are sufficient for the console, tests and offline evidence verification. No download or API key is needed for those checks.

To reproduce external predictions locally after reviewing the source terms:

```sh
.venv/bin/python -m pip install -e '.[ml,app,data]'
.venv/bin/python scripts/fetch_external.py --accept-source-terms
.venv/bin/python -m promptgate prepare --source data/raw --output data/processed/reproduction
.venv/bin/python -m promptgate.ml train --data data/processed/reproduction --raw-train data/raw/prompt_injection_train.csv --models models/reproduction
.venv/bin/python -m promptgate.ml benchmark --data data/processed/reproduction --models models/reproduction --output results/runs/reproduction
```

Use new output directories on subsequent runs; the pipeline refuses to overwrite frozen evidence. The fetch helper copies included S-Labs originals into `data/raw/`, obtains only the two deepset Parquet files, verifies hashes and refuses to replace differing existing files. That directory remains Git-ignored. Training is CPU-only and uses the pinned scikit-learn version. Runtime latency and model serialisation bytes may differ across machines; compare decision counts and policy, not timing equality.
