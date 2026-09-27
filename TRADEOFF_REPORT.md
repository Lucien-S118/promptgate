# PromptGate: business and technical trade-offs

**Student:** Siwen Liu  
**Course:** PE6201 Emerging AI Technologies  
**Project:** PromptGate

## Problem and users

Enterprise RAG assistants accept natural-language inputs from employees and customers. A malicious prompt can ask the assistant to ignore its governing instructions, expose hidden context, or bypass safety controls. A normal keyword rule catches obvious phrases but misses paraphrases and creates a brittle maintenance burden. The users of PromptGate are the application owner, who needs a measurable control before the RAG call, and the reviewer, who handles uncertain cases. The end user receives no model-generated authority to bypass the gate.

## Proposed AI system

PromptGate is a narrow text-classification gateway. It returns `Allow`, `Block`, or `Review`. A calibrated classifier and deterministic rules make the decision. `Review` is an abstention state rather than a hidden success category. An optional GPT-4o-mini call explains only why a Review item needs inspection. The explanation endpoint is available only after a classifier Review and its response is schema-validated as a reason; it cannot change the action or forward the input. This separation prevents a persuasive language-model answer from overriding a fixed safety policy.

## Build or buy

The gate is built because its policy boundary, data split, checksum verification, no-prompt logging, and fail-closed behavior must be inspectable. A hosted moderation or prompt-security API would reduce maintenance and may provide stronger operational support, but it would add vendor dependency, data-transfer and retention questions, opaque threshold behavior, and recurring per-call cost. The project therefore uses a small locally loaded model for the primary decision and keeps the language model in a narrow explanation role. OpenRouter is used only for the separately measured MVP and optional Review explanation, not for the authoritative classifier action.

## Data and evaluation

The teacher-requested training run uses the original 11,089-row S-Labs training CSV. A disjoint validation portion is split into calibration and policy-selection halves. The threshold is selected on the policy half at a 5% FPR cap; the four texts overlapping the original training CSV are removed from calibration/policy selection. The 662-row deepset data is reserved for external evaluation because its dataset card has inconsistent license metadata. It is not redistributed and is never used to tune the threshold. The repository records hashes and split decisions, while raw datasets remain outside the repository.

The selected Naive Bayes model achieved 99.6% attack block recall and 4.0% benign FPR on its development policy split. On the frozen external set it blocked 210 of 263 attacks (79.8%) and falsely blocked 172 of 399 benign inputs (43.1%). The external FPR is the measured value, not an imposed cap. Logistic regression reduced external FPR to 16.0% but also reduced attack recall to 69.2%. A Review margin lowered some automatic errors but still had 36.8% external FPR and sent 27.9% of items to human review. This is evidence of dataset shift and a real operational trade-off, not evidence that the target was met.

The separate 100-call GPT-4o-mini MVP run had zero technical failures, 50.0% attack block recall, 0% benign FPR, 13% Review rate, 3.42-second p95 latency, and US$0.0066129 provider-reported cost. It did not meet the historical 58.3% target. The result is kept separate from the offline classifier benchmark because the systems and data are different.

## Risks and controls

False positives create reviewer workload and can block legitimate work. False negatives can pass a prompt to the downstream assistant. Domain shift is demonstrated by the external FPR. The model sees only a standalone English input; it does not detect indirect injection in retrieved documents, conversation state, tool arguments, or model output. Scores are model signals rather than proof. Local no-logging does not establish provider non-retention for an optional external explanation call. Controls include a human Review state, strict input and output validation, checksum-verified model artifacts, fail-closed API errors, no hidden retries, and regression tests for policy conflicts and malformed model responses.

## Minimum viable version and next decision

The MVP is a local FastAPI console backed by the frozen Naive Bayes artifact, with the three fixed actions, risk score, reason, model checksum, and offline benchmark summary. It can be demonstrated without a paid API call. A realistic next iteration should collect an organization-specific labelled sample, set an operational FPR and review-capacity target with the application owner, reselect the threshold on that development distribution, and monitor drift before any production integration. The current evidence supports a research prototype and a strong measurement story; it does not support claiming production protection.
