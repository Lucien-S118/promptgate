# Evaluation explanation

## What the checked in evidence proves

`../evidence/offline/` contains all eight text-free prediction files, the complete metric summary and original protocol from `teacher-11089-external-20260925-01`. These are the measured regex, Naive Bayes, logistic and hybrid decisions on the 2,001-row S-Labs remaining test and 662-row deepset benchmark. `../evidence/live/` contains 100 text-free predictions and the full summary from `llm-mvp-20260922-01`. The two short summary files in `../evidence/` are convenient headline extracts; the full records are the source for recomputation.

The offline benchmark ran locally with trained models and no LLM calls. The live baseline made 100 actual OpenRouter calls. Optional Review explanations in unit tests use mocked provider responses: those tests prove code behaviour, not real-provider explanation quality. The final submission preparation does not rerun a paid evaluation or tune the frozen models.

Run from the repository root:

```sh
.venv/bin/python scripts/verify_evidence.py
.venv/bin/python -m unittest discover -s tests -v
```

The verifier checks packaged file hashes, source row counts, frozen model hashes, prediction counts, split memberships, full summaries and headline extracts. It recomputes paired Review error capture, screens the 100-row S-Labs MVP subset locally, and reproduces all 2,001 saved hybrid holdout decisions and scores using the frozen model. It has no network path and needs no credential. For full training/benchmark reproduction, follow [the data explanation](../data_sources/README.md).

## Decisions and denominators

- Attack block recall = attacks assigned Block / all labelled attacks.
- Benign block FPR = benign inputs assigned Block / all labelled benign inputs. Report the observed value, never cap external FPR at the development target.
- Review rate = all Review decisions / all inputs. Review does not count as a correct attack block.
- Attack hold rate = attacks assigned Block or Review / all attacks. This is not measured downstream attack prevention.
- Benign hold rate = benign inputs assigned Block or Review / all benign inputs. This exposes friction hidden by block FPR alone.
- The reported TP/FP/FN/TN and macro-F1 collapse actions to **Block versus not Block**. A benign Review contributes to TN in that binary view, but is not a successful automatic Allow. Use hold rate and Review rate alongside it.
- Review error capture = errors of the same frozen binary classifier that were routed to Review / all that classifier's errors before abstention. It is not measured human correction accuracy. Error precision = those captured errors / all Review cases.
- Technical failures remain in the denominator and are held, not dropped. p95 is nearest-rank latency. Cost is summed from reported usage; missing billed costs are unknown rather than zero.

## Frozen selection protocol

Model fitting uses the original 11,089 S-Labs rows. Sigmoid calibration uses 990 rows; threshold and margin selection use a separate 991 rows. Binary threshold maximises recall subject to 5% development FPR. Review margin is selected from 61 values between 0 and 0.30, maximising captured development errors subject to a 19% Review cap, then preferring lower review rate and smaller margin. Candidate selection compares development binary recall, then lower FPR. See `models/teacher-11089/training_protocol.json` and candidate metadata for exact settings.

The preparation audit reads dataset labels for integrity checks; selection itself does not use external outcomes. Public benchmark exploration predates the frozen run. This is not a preregistered blind benchmark or a claim of complete historical non-exposure.

## Key outcomes

| Frozen system and sample | Attack block recall | Benign block FPR | Review |
| --- | ---: | ---: | ---: |
| Regex, external 662 | 1.9% | 0.0% | 0.0% |
| Naive Bayes binary, policy 991 | 99.6% | 4.0% | 0.0% |
| Naive Bayes binary, external 662 | 79.8% | 43.1% | 0.0% |
| Logistic binary, external 662 | 69.2% | 16.0% | 0.0% |
| Hybrid selected Naive Bayes, external 662 | 76.4% | 36.8% | 27.9% |
| LLM baseline, separate balanced 100 | 50.0% | 0.0% | 13.0% |

For the external hybrid: 201 attacks Block, 37 Review, 25 Allow; 147 benign inputs Block, 148 Review, 104 Allow. Thus 90.5% of attacks and 73.9% of benign inputs are held; 53/225 binary errors are captured among 185 Reviews. The latter is 23.6% error capture and 28.6% error precision.

The target was at least 80% external attack recall and at most 5% benign FPR. It is not met. A high same-source score does not establish deployment readiness. The 100-call MVP also fails its historical 58.3% recall aspiration. Its 0/50 benign false positives are a small-sample observation, not proof of zero risk; its US$0.0066129 cost and 3.42 s p95 are not measurements of the optional explanation endpoint.

## Limitations

No human-review study, downstream RAG compromise experiment, adversarial adaptive attack campaign or real organisational workload was measured. Exact-text leakage checks do not eliminate semantic leakage. The original training rows include duplicates and a label conflict. Two candidates and a fixed margin grid are a limited search, not exhaustive optimisation. External labels and source language/style may differ; the observed gap is consistent with distribution shift but does not establish its precise cause. A different test sample for the live LLM means no valid head-to-head model ranking from the headline table. Future retuning must use new development data and a new holdout, not the already-inspected external benchmark.
