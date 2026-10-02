# Code and module guide

Start with `webapp.py` for the demo, `ml.py` for the trained policy, and `metrics.py` for the reported numbers. Module docstrings describe each responsibility; this index explains how they connect.

| File | Responsibility | Inputs and outputs | Important boundary |
| --- | --- | --- | --- |
| `promptgate/__init__.py` | Package identity | Package import | No inference on import |
| `promptgate/__main__.py` | CLI entry point | `scan`, `prepare`, `evaluate` commands | Hidden key entry or environment, never a command-line key |
| `promptgate/contracts.py` | Input and output validation | Prompt and JSON → validated `Screening` | Duplicate JSON keys, score/action conflicts and invalid inputs rejected or held |
| `promptgate/baselines.py` | Fixed regex comparator | Text → rule-only decision | Baseline is not an LLM; rules also support hybrid Review |
| `promptgate/data.py` | Source parsing and leakage audit | Original CSV/Parquet → JSONL splits and manifest | Versioned outputs; exact normalised-text deduplication, not semantic deduplication |
| `promptgate/ml.py` | Training, calibration, policy and benchmark | Labelled splits → model artifacts; prompt → decision | Development-only policy selection; `--raw-train` preserves instructor's 11,089 rows |
| `promptgate/metrics.py` | Shared metric definitions | Labelled prediction records → aggregate metrics | Review is not a successful attack block; errors remain in denominators |
| `promptgate/llm.py` | Initial one-call model baseline | Untrusted input → validated model output | One request, no hidden retry; malformed outputs are held |
| `promptgate/explanation.py` | Optional Review explanation | Fixed Review case → reason and usage | No action supplied by model; failures cannot approve input |
| `promptgate/evaluate.py` | Baseline run recording | Dataset and backend → predictions and summary | No raw prompts in prediction logs; incomplete runs remain incomplete |
| `promptgate/live_control.py` | Local credential-entry helper | Browser key entry → fixed MVP run | Loopback only; legacy evaluation helper, not needed for final demo |
| `promptgate/webapp.py` | Local HTTP service | `/screen`, `/explain-review`, `/health` | Rechecks Review eligibility server-side; no downstream forwarding endpoint |
| `promptgate/static/index.html` | Browser console | Form and JSON responses | Uses textContent; no persistent key storage; no authentication |
| `tests/test_promptgate.py` | Core regression tests | Synthetic fixtures and mock responses → pass/fail | No paid API calls |
| `tests/test_ml_webapp.py` | Policy and integration tests | Frozen models, mock explanations → pass/fail | Distinguishes model evidence from mocked provider behaviour |
| `tests/test_submission.py` | Submission and demo regression tests | Packaged records and actual demo inputs → pass/fail | No provider calls; checks all three live console actions |
| `scripts/verify_evidence.py` | Submission evidence audit | Included records and source snapshots → checks | Offline; fails on inconsistent counts, metrics or checksums |
| `scripts/fetch_external.py` | Optional external-data acquisition | Pinned upstream files → ignored local Parquet | Explicit opt-in; verifies original hashes; no raw external text committed |
| `scripts/package_evidence.py` | Package original local runs | Existing data and results → checked-in snapshots | Not a new experiment; refuses changed evidence |
| `scripts/build_report.py` | Produce editable report | Markdown report → Word document | Optional python-docx dependency; no role in runtime inference |

## Safe reviewer path

Install the extras in the main README, run the test suite, run the offline evidence verifier, then start the console. Neither the console's screening path nor the verifier requires a key. The optional LLM path uses a provider network call and must not be confused with mocked tests.

## Reproducibility boundary

The model protocol preserves source hashes from the original training run. Documentation changes after training do not retroactively change that historical record. Frozen models and policies are not retuned for the final submission. Model file hashes are validated before trusted local loading; install the pinned scikit-learn version for compatibility.
