# PromptGate: business and technical trade-offs

**Student:** SIwen Liu
**Course:** PE6201 Emerging AI Technologies  
**Project:** PromptGate

## Problem, user and scope

I am addressing one problem: hostile or instruction-overriding prompts can reach an enterprise RAG assistant before anyone checks them. My primary user is Mei, an AI engineer releasing a RAG assistant who understands ML metrics but cannot inspect every input. With PromptGate, she forwards `Allow` cases and sends `Review` cases to a human; she does not treat a model explanation as permission. The prototype screens one standalone English input before retrieval. It does not inspect retrieved documents, conversation state, model output, tools, or user identity.

## AI design and build/buy decision

I chose a hybrid rather than a regex-only system. Rules catch obvious phrases, while a narrow labelled classifier handles more varied text. The classifier owns the `Allow`, `Block`, or `Review` decision. I first built the smallest end-to-end baseline from the Problem Statement: one prompt, one GPT-4o-mini structured-output call through OpenRouter, and one validated result. I then added the narrow classifier, calibration, Review routing and the local console as the final extension. GPT-4o-mini explains a Review case only; the explanation endpoint is unavailable for other actions and cannot change the action or forward the input.

I own the interface and FastAPI serving, orchestration, classifier policy, data preparation, evaluation and observability because these are the project-specific controls. I rent the commodity foundation model through OpenRouter only for the baseline and optional Review explanation. I do not rent retrieval because retrieval is outside scope. This keeps the safety decision checkable and places the LLM outside the safety-critical path. I chose code over a low-code builder because threshold selection, split isolation and failure behaviour need tests and checksums. The live baseline used 100 calls, cost US$0.0066129 in provider-reported usage, and had 3.42 seconds p95 latency, or about US$0.000066 per call. The classifier path is local and adds no per-input API cost.

## Data and evaluation

I trained on the original 11,089-row S-Labs prompt-injection training CSV, where the labels are benign versus injection. The 2,101-row validation split is divided into calibration and policy-selection halves. Four texts overlapping the original training CSV are removed from validation selection to avoid leakage. I selected the threshold on the policy half at a 5% benign FPR cap, then froze the model and policy before reading external labels. The external deepset set has 662 rows (263 attacks and 399 benign). Its dataset card has inconsistent licence metadata, so I use it for local evaluation only and do not redistribute it. The raw data stays outside the repository; trained weights, evidence summaries and a reproduction README are shipped.

My primary metric is attack block recall at an agreed benign FPR, because a missed injection is the main security failure. The deterministic regex baseline on the external set blocked 1.9% of attacks with 0% FPR. The majority-class accuracy there is 60.3%, so accuracy alone would be misleading. The selected Naive Bayes classifier-only comparison reached 99.6% attack recall and 4.0% FPR on the 991-row development policy split. On the frozen external set it blocked 210/263 attacks (79.8%) and falsely blocked 172/399 benign inputs (43.1%). Logistic regression lowered external FPR to 16.0% but also lowered attack recall to 69.2%.

The actual web application uses the hybrid Review policy layered on the selected Naive Bayes scores. On the same external set it blocked 201/263 attacks (76.4%), falsely blocked 147/399 benign inputs (36.8%), and sent 185/662 inputs (27.9%) to Review. Review captured 53 of 225 counterfactual binary errors (23.6%) before abstention. These numbers show distribution shift rather than a passed 5% production target. The separate 100-call GPT-4o-mini baseline had 50.0% attack block recall, 0% FPR, 13% Review rate and zero technical failures; it did not reproduce the historical 58.3% reference. I keep those results separate because the data and decision mechanisms differ.

## Risks, mitigations and responsible use

False positives can block legitimate work; the mitigation is an explicit `Review` route, a measured review-rate budget and a human confirmation step. False negatives can expose the downstream assistant; the mitigation is a held-out external benchmark, a red-team regression set and fail-closed handling of uncertain or malformed outputs. A silent confident error can go unnoticed; the mitigation is versioned test data, checksum-verified model artifacts and future drift monitoring. Provider retention is outside local control; the mitigation is to use public or synthetic test text for the optional external call and to document that local no-logging is not provider non-retention. The intended use is pre-inference support for authorised enterprise AI engineers under the OWASP Top 10 for LLM Applications (2025); it is not a production guarantee, autonomous action system or full indirect-injection defence.

## Minimum viable version

The first working slice is one English prompt to one GPT-4o-mini structured-output call to one `Allow`/`Block`/`Review` result with a score and reason. It completed 100 real calls without technical failure, but reached only 50.0% attack block recall on the fixed sample, so the stated 58.3% MVP target was not met. The current local FastAPI console is the smallest useful extension: it runs the frozen classifier, displays the decision and score, and requires a human for Review without a paid API call. Before production, I would collect organisation-specific labels, agree on acceptable FPR and review capacity, reselect the threshold on that development distribution, and monitor drift.
