<!-- Generated from the pinned source PDF. Do not edit manually; rerun this script. -->
# Knowing When to Stop: Bayesian Optimal Stopping for LLM Evaluations

This is a source-derived agent-facing extraction for the Core Reproduction v1 task. The main methods, experimental setup, formal Appendix A material, limitations, and references are retained. The empirical Appendix B is withheld as a unit because its pages interleave result-bearing validation with prose. Answer-bearing empirical results are replaced with explicit placeholders.

<!-- Source page 1 -->
# Knowing When to Stop: Bayesian Optimal Stopping for LLM Evaluations

## Abstract

[RESULTS REDACTED: abstract outcome claims]

1 Introduction
1.1 Problem Statement
The evaluation of large language models has become a central pillar of AI safety assurance, with major laboratories,
regulatory bodies, and independent auditors conducting increasingly comprehensive testing campaigns to characterise
model capabilities and risks prior to deployment (see, e.g., [32, 3]). Frontier models are now routinely assessed across
hundreds of distinct tasks spanning reasoning, factual knowledge, coding, multilingual competence, and safety-relevant
behaviours [23, 33], with individual benchmarks such as BIG-bench comprising over 200 tasks [33] and HELM
evaluating models across 42 scenarios [23].
Each task typically entails hundreds or thousands of test items, and the stochastic nature of language model generation
necessitates multiple repetitions per item to obtain stable performance estimates. For a suite of 200 tasks with 1,000
items and 5 repetitions each, a single model requires one million inference calls - before accounting for comparisons
across model families or evaluation conditions. This computational burden is compounded by the rapid pace of
model development: new releases demand fresh evaluation, while meaningful benchmarking often requires re-testing
predecessors under identical conditions [19, 12]. As suites expand to address agentic behaviours [20] and multi-step
tasks requiring tool use [26], the resource demands grow correspondingly.
Yet despite these costs, current evaluation practices predominantly follow what has been termed the “highest-number-is-
best approach” [27, 24]: reporting point estimates of aggregate performance without systematic uncertainty quantifica-
tion, appropriate treatment of hierarchical data structure, or formal statistical validation [8].
This trajectory raises a fundamental methodological question: are current evaluation practices systematically miscali-
brated, expending computational resources beyond what statistical inference requires? Or conversely, terminating data
collection before reliable conclusions can be drawn? If so, the inefficiency - or the inferential risk - scales with every
new model and every expanded benchmark suite.
arXiv:2608.14425v1  [cs.AI]  14 Aug 2026

<!-- Source page 2 -->
optstop
1.2 Statistical Sufficiency in Evaluations
Understanding why current evaluation practices may be miscalibrated requires examining the statistical structure of
LLM assessment and the inferential demands it places on practitioners. Evaluation data possess a naturally nested
hierarchy: individual responses are generated for specific items (prompts or problems), which are grouped within
tasks or subdomains, which in turn cluster within broader capability domains, with the entire structure replicated
across multiple models under assessment [24], see Figure 1. At the finest grain, repeated queries of the same item can
yield different responses, necessitating multiple epochs per item to distinguish capability from sampling noise. This
hierarchical structure is pervasive across evaluation contexts yet rarely accorded appropriate statistical treatment.
Figure 1: Example hierarchically nested structure of evaluation data. Taken from [24].
Compounding this structural complexity is the heterogeneity of performance across the evaluation space. Model
capabilities do not degrade or improve uniformly: the “jagged frontier” phenomenon - borrowing a metaphor from
Dell’Acqua et al.’s study of AI-augmented professional tasks [13] - describes how a model may excel at one capability
while failing at a superficially similar one.
Performance varies across tasks, difficulty levels, prompt formulations, and their interactions, and the uncertainty in any
evaluation is itself uneven: some model-task combinations yield consistent results after few observations, while others
exhibit high variance that demands extended sampling to resolve. Moreover, current practice applies uniform sampling
regimes regardless of inferential goal or intrinsic variability.
Conventional frequentist approaches - sample means with standard errors or confidence intervals - presuppose large
samples, approximate normality, and variance homogeneity, assumptions routinely violated in evaluation contexts with
sparse, non-continuous, or heterogeneous data [24, 27]. Hierarchical Bayesian models address these limitations by
explicitly representing the nested structure of evaluation data, enabling partial pooling across levels [14]. Posterior
credible intervals provide valid uncertainty quantification even in low-data regimes, without asymptotic assumptions.
The HiBayES framework [24] has demonstrated these advantages for LLM evaluation specifically, showing more
calibrated uncertainty estimates and more robust inferences than conventional methods.
This paper introduces optstop, a precision-based optimal stopping framework for LLM evaluation that similarly
leverages hierarchical Bayesian principles. Where frameworks such as HiBayES address the analysis of evaluation
data after collection - answeringwhat does this data tell us?- optstop addresses the logically prior question:when
can data collection safely stop?The package implements adaptive sequential stopping rules that monitor the width
of Bayesian credible intervals during evaluation, automatically terminating data collection for individual items and
model-task groupings once estimates reach a user-specified precision.
2

<!-- Source page 3 -->
optstop
1.3 The Value of Efficiency in Testing
The stopping question reduces to a resource allocation problem: how to maximise the expected information gain from
the next observation. As posterior uncertainty decreases non-uniformly across the evaluation space, an efficient strategy
terminates collection where precision is adequate and concentrates effort where uncertainty persists.
This principle has immediate practical consequences. The direct costs of comprehensive evaluation are substantial
- single tasks in some agentic benchmarks consume tokens worth hundreds of US dollars [10, 24] - and these costs
shape what gets evaluated, forcing trade-offs between breadth of coverage and depth of assessment. Evaluation latency
constrains safety assurance cycles, compressing the window for remediation and deliberation [32]. Beyond cost
and time savings, efficiency has implications for environmental sustainability [28] and equitable access to rigorous
evaluation. Most consequentially, adaptive stopping transforms evaluation from a fixed-budget exercise into one of
targeted reallocation: computational effort freed from well-characterised model-task combinations can be redirected
toward capability boundaries and rare-event scenarios where uncertainty - and safety relevance - is greatest.
1.4 Related Work
Several complementary strategies for improving LLM evaluation efficiency have emerged.Adaptive item selection
methods, grounded in Item Response Theory (IRT) and Computerized Adaptive Testing (CAT), reduce evaluation cost
by selecting maximally informative test items for each model. Perlitz et al. [29] demonstrate that reliable benchmark
rankings can be obtained from a fraction of evaluation items. Hofmann et al. [16] combine IRT-based ability estimation
with dynamic item selection, and Li et al. [22] use Fisher information-guided item selection to reduce required items
by up to 90%. Balkır et al. [4] extend adaptive testing to continuous scores with precision-based stopping. These
approaches reduce thebreadthof evaluation (fewer items per model) but typically require a pre-calibrated item bank,
which may not exist for novel benchmarks or safety-critical tasks where comprehensive coverage is required.
A separate line of work applies optimal stopping toinference-timesampling: determining when to stop generating
candidate responses for a given prompt. Wan et al. [36] use Bayesian sequential search, while Kalayci et al. [17] apply
Pandora’s Box models. These optimise generation quality, not evaluation design.
The present work occupies a distinct niche: automated, real-time stopping decisionsduringevaluation runs, determining
when collected data are sufficient for reliable inference at both the item and grouping levels, without requiring
pre-calibrated item parameters or modifications to evaluation content.
2 TheoptstopFramework
The optstop package is a Python library, publicly available as a GitHub repository ( https://github.com/
UKGovernmentBEIS/optstop). It integrates with the inspect_ai evaluation framework [34] as a live early stopping
protocol, and also functions as a standalone tool for retrospective analysis of completed datasets.
2.1 Precision-Based Stopping
The core stopping criterion evaluates whether the width of the posterior credible interval for a performance parameter
has fallen below a user-specified precision thresholdδ. Let W=θ U−θL denote the width of the (1−α) credible
interval for parameterθ; stopping occurs whenW <δ. The framework operates at two levels: one threshold governs
stopping at the individual item level (when sufficient repeated evaluations have been collected for a given prompt), and
a second governs stopping at the grouping level (when sufficient items have been evaluated for a given model-task
combination). A threshold ofδ= 0.05 implies precision to within±2.5 percentage points at the specified credibility
level (default 97%).
A secondarystabilisation criteriondetects when further data collection yields diminishing inferential returns. This
criterion monitors the slope of recent CI width values within a sliding window, declaring stabilisation when the slope is
near zero and not trending toward steeper descent. It serves as a fallback for settings where the width threshold would
require impractically many observations (see Appendix A.1.2 for formal specification).
Valid application requires two conditions: exchangeability of observations within each grouping (their joint distribution
should be invariant to permutation), and randomised item presentation order. The inspect_ai framework supports the
latter through its sample_shuffle option (not enabled by default, but recommended as a precautionary measure when
the evaluator cannot guarantee that item ordering is independent of difficulty or other confounds). Evaluators using
optstopindependently should ensure equivalent randomisation.
3

<!-- Source page 4 -->
optstop
2.2 Conservatism
A systematic risk attends any early stopping procedure: premature termination before rare but important events have
been observed. In LLM evaluation this risk is most acute for capability detection - a model that succeeds on only
1% of attempts warrants substantially more cautious stopping than one succeeding 99% of the time. This concern
connects directly to the pass@k evaluation paradigm [9], where even a single success acrossk attempts demonstrates
qualitatively different capability than consistent failure.
The package addresses this through an asymmetric conservatism adjustment applied when estimated performance falls
below a low threshold (default 1%): the effective credible interval width used for the stopping comparison is multiplied
by a conservatism factor (defaultc= 5 ), and the slope threshold for the stabilisation criterion is tightened by the same
factor. This delays stopping for low-performing combinations, providing additional opportunity for rare successes to be
observed, without penalising evaluations where performance is clearly high. A sensitivity analysis of this mechanism
across calibrated performance levels appears in Appendix B.11.
2.3 Hierarchical Inference and Groupings
Evaluation data have a naturally nested structure: individual responses are nested within items (distinct prompts), which
nest within groupings (model-task combinations). The framework operates simultaneously at both levels. At the item
level, Bayesian inference characterises performance on each individual prompt across its repeated evaluations. At the
grouping level, a hierarchical Bayesian model partially pools information across items, yielding stable estimates even as
individual items terminate at different points.
Groupings are user-defined partitions of the evaluation space; each grouping maintains its own inference state and
triggers stopping criteria independently. A factorial grouping design based on all manipulated factors that may
systematically affect performance is generally recommended (e.g., model× task, or model× task× difficulty). Finer
groupings provide higher resolution but require more observations to achieve precision thresholds; coarser groupings
converge faster but may obscure performance heterogeneity.
Table 1: Summary of the three inference pathways. µ0 = 0 by default; the prior scales shown are the pathway
defaults (both configurable via prior_mu and prior_sigma);µgroup,σgroup, andϕgroup denote the group-level mean,
between-item scale, and precision parameters respectively. Stopping thresholds apply at both item and grouping levels,
and the asymmetric conservatism adjustment (Section 2.2) applies to all three pathways when estimated performance
falls below the low-performance threshold. Full specifications - including item-level priors, cutpoint parameterisation,
and the priors of the Dirichlet-Multinomial fallback model - are given in Appendix A.4.
Binary Ordinal Continuous bounded
Scores 0/1 (correct/incorrect) Ordered categories0,...,K−1
(e.g., 0–10 rubric,K= 11)
Bounded continuous,
normalised to[0,1]
Routing Default pathwayordinal_tasksname matching
(inspect_aiand standalone)
score_aggaggregation
(inspect_ai) or
continuous_tasksname
matching (standalone)
Item-level model Adaptive Beta (data-dependent
prior)
Bayesian bootstrap over the modal
category
Beta via method-of-moments
Grouping-level
model
Logit-normal hierarchical Hierarchical ordered logistic
(cumulative link);
Dirichlet-Multinomial fallback
Logit-normal hierarchical on
item-level means
Group-level priorsµ group∼Normal(µ 0,1.5);
σgroup∼Exponential(1)
µgroup∼Normal(µ 0,2);
σgroup∼Exponential(1)
µgroup∼Normal(µ 0,1.5);
σgroup∼Exponential(1);
ϕgroup∼Gamma(2,1)
Estimand Population mean success
probability
Modal category of the
item-averaged distribution
Population mean of item-level
means
Stopping criteria CI width<δ; stabilisation
criterion as fallback
Hybrid: modal CI width<δgated
on low entropy (Pathway 1), or
entropy CI width below
convergence threshold (Pathway 2)
CI width<δon the normalised
scale; stabilisation criterion as
fallback
4

<!-- Source page 5 -->
optstop
2.4 Inference Pathways
The package supports three score types through tailored inference pathways, with distributional assumptions appropriate
to the data type. Routing is determined by user configuration: binary inference is the default; ordinal inference is
activated by declaring which tasks use ordered categorical scoring; and continuous inference is activated for tasks using
score aggregation functions or continuous metrics. Table 1 summarises the three pathways.
Binaryscores (correct/incorrect) are modelled with a logit-normal hierarchical structure at the grouping level, selected
over the conjugate Beta-Binomial for computational reliability (see Appendix B.6 for simulation evidence). The
estimand is the population-level mean success probability.
Ordinalscores (discrete ordered categories, e.g., 0–10 rubrics) are modelled using a hierarchical ordered logistic
(cumulative link) model, with a Dirichlet-Multinomial fallback when ordered assumptions are inappropriate. The
estimand is the modal category of the item-averaged category distribution. Stopping employs a hybrid of two pathways:
Pathway 1requires both a narrow modal credible intervalandlow distributional entropy, confirming a genuinely peaked
distribution rather than a spurious narrow interval from sparse data;Pathway 2evaluates whether the entropy credible
interval width has fallen below a convergence threshold, handling distributions that are legitimately diffuse and lack a
clear mode.
Continuous boundedscores (e.g., normalised similarity metrics, mean rubric aggregates) are modelled using a
hierarchical logit-normal structure operating on item-level summary statistics rather than individual observations,
providing approximately 20×theoretical computational speedup relative to observation-level inference.
3 Empirical Validation
To evaluate whether the stopping framework preserves statistical validity across inference pathways and the performance
spectrum, we conducted a 3×3 matrix experiment crossing three inference pathways (binary, ordinal, and continuous;
Table 1) with three performance levels (ˆp:low, mid, and high). Each cell was run inshadow mode- executing all 2,000
planned trials while internally tracking when stopping criteria would have been met. To isolate the pure truncation
effect, we compare the score computed from the full run against the score computed from only those trials that would
have been collected up to the stopping decision, eliminating between-run variance from LLM stochasticity.
The binary column employed distinct benchmarks and models to achieve natural performance variation: MATH Level 5
with GPT-3.5 Turbo (low,ˆp≈0.05), GPQA Diamond with GPT-4o (mid, ˆp≈0.50), and MMLU 0-shot with GPT-4o
(high, ˆp≈0.83 ). The ordinal and continuous columns used WritingBench [37] with Claude Sonnet 4.5 1, varying
max_tokens (50, 500, 5,000) to modulate performance across an 11-category rubric (K= 11 , scores 0–10). All cells
used 200 items (198 for mid-binary, the full GPQA Diamond set), 10 epochs per item, a precision threshold ofδ= 0.05 ,
and 97% credible intervals (see Appendix B.8.1 for full experimental protocol).

## 3.1 Stopping Efficiency and Score Fidelity

[RESULTS REDACTED: empirical metrics, comparisons, and conclusions]


<!-- Source page 6 -->
[RESULTS REDACTED: result-bearing main-text analysis, figures, and conclusions]

<!-- Source page 7 -->
[RESULTS REDACTED: result-bearing main-text analysis, figures, and conclusions]

<!-- Source page 8 -->
[RESULTS REDACTED: result-bearing main-text analysis, figures, and conclusions]

<!-- Source page 9 -->
optstop
[16] Valentin Hofmann et al. “Fluid Language Model Benchmarking”. In:Proceedings of the Conference on Language
Modeling (COLM). 2025.URL:https://arxiv.org/abs/2509.11106.
[17] Yusuf Kalayci, Vinod Raman, and Shaddin Dughmi. “Optimal Stopping vs Best-of- N for Inference Time
Optimization”. In:arXiv preprint arXiv:2510.01394(2025).URL:https://arxiv.org/abs/2510.01394.
[18] Ken Kelley and Joseph R Rausch. “Sample size planning for the standardized mean difference: accuracy in
parameter estimation via narrow confidence intervals.” In:Psychological methods11.4 (2006), p. 363.
[19] Douwe Kiela et al. “Dynabench: Rethinking benchmarking in NLP”. In:Proceedings of the 2021 conference of
the North American chapter of the Association for Computational Linguistics: human language technologies.
2021, pp. 4110–4124.
[20] Megan Kinniment et al. “Evaluating language-model agents on realistic autonomous tasks”. In:arXiv preprint
arXiv:2312.11671(2023).
[21] John K. Kruschke and Torrin M. Liddell. “The Bayesian New Statistics: Hypothesis testing, estimation, meta-
analysis, and power analysis from a Bayesian perspective”. In:Psychonomic Bulletin & Review25.1 (2018),
pp. 178–206.
[22] Peiyu Li et al. “Adaptive Testing for LLM Evaluation: A Psychometric Alternative to Static Benchmarks”. In:
arXiv preprint arXiv:2511.04689(2025).URL:https://arxiv.org/abs/2511.04689.
[23] Percy Liang et al. “Holistic evaluation of language models”. In:arXiv preprint arXiv:2211.09110(2022).
[24] Lennart Luettgau et al. “HiBayES: A Hierarchical Bayesian Modeling Framework for AI Evaluation Statistics”.
In:arXiv preprint arXiv:2505.05602(2025).
[25] Peter McCullagh. “Regression models for ordinal data”. In:Journal of the Royal Statistical Society: Series B
(Methodological)42.2 (1980), pp. 109–127.
[26] Grégoire Mialon et al. “Gaia: a benchmark for general ai assistants”. In:The Twelfth International Conference
on Learning Representations. 2024.
[27] Evan Miller. “Adding error bars to evals: A statistical approach to language model evaluations”. In:arXiv
preprint arXiv:2411.00640(2024).
[28] David Patterson et al. “Carbon Emissions and Large Neural Network Training”. In:arXiv preprint
arXiv:2104.10350(2021).URL:https://arxiv.org/abs/2104.10350.
[29] Yotam Perlitz et al. “Efficient Benchmarking (of Language Models)”. In:Proceedings of the 2024 Conference of
the North American Chapter of the Association for Computational Linguistics (NAACL). 2024.URL: https:
//arxiv.org/abs/2308.11696.
[30] Donald B Rubin. “The bayesian bootstrap”. In:The annals of statistics(1981), pp. 130–134.
[31] Felix D Schönbrodt et al. “Sequential hypothesis testing with Bayes factors: Efficiently testing mean differences.”
In:Psychological methods22.2 (2017), p. 322.
[32] Toby Shevlane et al. “Model evaluation for extreme risks”. In:arXiv preprint arXiv:2305.15324(2023).
[33] Aarohi Srivastava et al. “Beyond the imitation game: Quantifying and extrapolating the capabilities of language
models”. In:Transactions on machine learning research(2023).
[34] UK AI Safety Institute.inspect_ai: A Framework for Large Language Model Evaluations. Version 0.3. 2024.
URL:https://github.com/UKGovernmentBEIS/inspect_ai.
[35] Abraham Wald. “Sequential method of sampling for deciding between two courses of action”. In:Journal of the
American Statistical Association40.231 (1945), pp. 277–306.
[36] Guangya Wan et al. “BEACON: Bayesian Optimal Stopping for Efficient LLM Sampling”. In:arXiv preprint
arXiv:2510.15945(2025).URL:https://arxiv.org/abs/2510.15945.
[37] Yuning Wu et al. “WritingBench: A Comprehensive Benchmark for Generative Writing”. In:arXiv preprint
arXiv:2503.05244(2025).
A Technical Methods: Stopping Framework
A.1 Precision-based Stopping
The challenge of determining adequate sample sizes has occupied statisticians since the early twentieth century.
Classical power analysis [11] addresses this prospectively, calculating required samples to detect effects of specified
size with desired probability. However, such approaches assume knowledge of effect sizes and variance structures
that may be unavailable or inappropriate in the context of LLM evaluation, where performance characteristics vary
dramatically across models, tasks, and prompt formulations.
9

<!-- Source page 10 -->
optstop
An alternative tradition - sequential analysis - permits sample size determination during data collection rather than
before it. Pioneered by Wald [35] in the context of quality control, sequential methods evaluate accumulating evidence
after each observation and terminate sampling when a decision criterion is satisfied. This approach offers substantial
efficiency gains when the underlying signal is strong, as fewer observations are needed to reach confident conclusions.
A key justification for adopting a Bayesian framework for sequential stopping is the Stopping Rule Principle [5, 6]:
because the posterior depends only on the likelihood and prior, Bayesian inferences are valid regardless of the rule
governing when data collection ceased.
Within sequential analysis, two broad families of stopping rules have emerged. Inference-based stopping rules terminate
sampling when sufficient evidence exists to decide between competing hypotheses - for instance, when a Bayes factor
exceeds a threshold [31] or when a posterior probability crosses a decision boundary [7]. Such rules are well-suited to
confirmatory contexts where the goal is to adjudicate between pre-specified alternatives.
Precision-based stopping rules, by contrast, terminate sampling when parameter estimates achieve desired accuracy,
typically operationalised as confidence or credible interval width falling below a threshold [18]. This approach aligns
naturally with the exploratory and descriptive goals common in LLM evaluation, where the objective is often to
characterise model performance with adequate precision rather than to test specific hypotheses. When an evaluator
seeks to determine “how well does this model perform on task X?”, the natural stopping point is when that performance
estimate is sufficiently precise for the intended use - whether for model comparison, capability reporting, or safety
assessment.
The optstop package implements precision-based stopping within a Bayesian inferential framework. Bayesian
methods offer several advantages in this context: natural quantification of uncertainty through posterior distributions,
coherent updating as data accumulate, and principled handling of small samples through prior regularisation. The core
logic proceeds as follows: after each batch of observations, posterior distributions over performance parameters are
computed via Markov Chain Monte Carlo sampling using PyMC [1], credible intervals are derived, and stopping criteria
are evaluated. Sampling continues until precision thresholds are met or alternative termination conditions are satisfied.
Two critical assumptions underlie valid application of this framework to LLM evaluation. First, exchangeability within
groupings: observations within a defined grouping (e.g., a specific model-task combination) should be exchangeable in
the statistical sense - their joint distribution should be invariant to permutation. This assumption is generally reasonable
when evaluation items are drawn from a well-defined population and model behaviour is consistent across the evaluation
session. Second, randomised presentation order: the sequence in which items are evaluated should not systematically
bias early versus late observations. The inspect_ai framework supports this through its sample_shuffle option
(which accepts an optional seed for reproducibility), but shuffling is not enabled by default. This is particularly important
when item IDs within a grouping are expected to systematically differ by incrementing ID (e.g., difficulty progression).
Evaluators using optstop - whether through inspect_ai or independently - should ensure randomised item ordering.
Violations of these assumptions - for instance, through adaptive item selection or model drift during evaluation - may
compromise the validity of stopping decisions.
A.1.1 Credible Interval Widths
The primary stopping criterion in optstop evaluates whether the width of the posterior credible interval for a perfor-
mance parameter has fallen below a user-specified threshold. Formally, let θ denote the parameter of interest (e.g.,
success probability for a binary task), and let [θL,θU] denote the (1−α) credible interval derived from the posterior
distributionp(θ|data). At the grouping level, this is the highest density interval (HDI); at the item level, equal-tailed
quantile intervals are used for computational efficiency (see pathway-specific details in Appendix A.4). The credible
interval width is simply:
W=θ U−θL
Stopping occurs when W < δ, where δ is the precision threshold specified by the user. The package exposes two
such thresholds: delta_item governs stopping at the individual item (sample) level (determining when sufficient
epochs (repetitions) have been collected for a given item), while delta_cap governs stopping at the grouping level
(determining when sufficient items have been evaluated for a given model-task combination). The interpretation of
these thresholds should be calibrated to the evaluator’s practical requirements. A threshold ofδ= 0.05 implies that the
performance estimate is precise to within±2.5 percentage points at the specified credibility level (default 97%, chosen
to provide wider coverage than the frequentist 95% convention while avoiding the efficiency cost of 99% intervals). For
high-stakes safety evaluations requiring fine discrimination between models, tighter thresholds may be appropriate; for
preliminary capability surveys, looser thresholds may suffice. Note that the threshold represents a precisiontargetrather
than an accuracy guarantee - the interval is narrow, but its location depends on the observed data. Furthermore, the
nominal credibility level assumes the hierarchical model is well-specified; in practice, coverage depends on sample size
10

<!-- Source page 11 -->
optstop
and the proximity of true performance to boundaries. For smaller samples or near-boundary performance, hierarchical
shrinkage may cause intervals to undercover relative to nominal levels (see Appendix B.10 for empirical assessment).
The efficiency gains from this criterion depend on the underlying performance level and its variance. When performance
is very high, posterior distributions concentrate rapidly and narrow credible intervals are achieved with fewer observa-
tions. When performance is very low, posteriors also concentrate rapidly, but this apparent precision may be misleading:
rare successes may not yet have been observed, warranting the additional caution detailed in Appendix A.1.3. When
performance is moderate (near 50% for binary outcomes) or highly variable, more observations are required. This
behaviour is statistically appropriate: genuinely uncertain situations warrant more evidence, while clear-cut cases can
be resolved quickly.
A.1.2 Stabilisation Criterion
The credible interval width criterion assumes that continued sampling will eventually yield a sufficiently narrow interval.
While credible intervals necessarily converge given sufficient data, the convergence rate varies substantially with the
underlying variability (as described above). In cases where convergence to the user’s precision threshold would require
impractically many observations - for instance, under high between-item heterogeneity or when the threshold is tight
relative to the inherent posterior variance - additional sampling yields progressively diminishing precision gains. To
address such cases, optstop implements a secondary stopping criterion based on credible interval stabilisation. Rather
than requiring the interval to be narrow in absolute terms, this criterion evaluates whether the interval width has ceased
to decrease meaningfully with additional data - a signal that further sampling offers diminishing inferential returns.
The stabilisation criterion operates by tracking the trajectory of credible interval widths across successive inference
updates. LetW1,W 2,...,W t denote the sequence of interval widths computed at each update. A linear regression is
fitted to recent values within a sliding window of sizek(controlled by thestab_windowparameter), yielding a slope
estimate ˆβrepresenting the rate of change in interval width:
ˆβ=
Pk
i=1(i− ¯i)(Wt−k+i− ¯W)
Pk
i=1(i− ¯i)2
Stabilisation is declared when| ˆβ|<ϵ , whereϵ is controlled by the CI_delta parameter. Additionally, to guard against
premature stabilisation declarations due to transient plateaus, the criterion requires that the slope trajectory itself has
stabilised - specifically, that the slope is not trending toward steeper descent, which would indicate that precision gains
are accelerating rather than diminishing. The stabilisation check also requires at least four accumulated slope estimates
before evaluation, preventing noisy early estimates from triggering premature declarations.
This dual-criterion approach - absolute width or stabilised width - ensures that stopping decisions are appropriate across
diverse performance distributions. Clear-cut cases with concentrated posteriors trigger the width criterion; ambiguous
cases with irreducible uncertainty trigger the stabilisation criterion once further data collection becomes uninformative.
A.1.3 Conservatism and pass@K
A systematic risk attends any early stopping procedure: premature termination may occur before rare but important
events have been observed. In LLM evaluations, this risk manifests acutely in the assessment of difficult tasks where
model success is infrequent. Consider evaluating a model’s ability to solve challenging mathematical proofs, where the
model might succeed on only 5% of attempts. An early stopping rule optimising for precision might terminate sampling
after observing a string of failures, concluding with high confidence that the success rate is near zero - potentially
missing the model’s genuine (if limited) capability. This concern connects to the pass@k evaluation paradigm [9], where
model capability is assessed by whether at least one success occurs acrossk independent attempts. Under pass@k, rare
successes carry substantial inferential weight: a model that succeeds once in twenty attempts demonstrates qualitatively
different capability than one that never succeeds. Early stopping procedures must therefore exercise particular caution
when observed performance is low, as the most decision-relevant observations (rare successes) are precisely those least
likely to have occurred in limited samples. The optstop package addresses the most acute form of this risk - when
estimated performance is at or near zero, suggesting the model may have no genuine capability on the task - through
an asymmetric conservatism adjustment applied when estimated performance falls below a threshold (controlled by
low_performance_threshold, defaulting to 1%). When this condition is met, stopping criteria are modified to
require stronger evidence before termination:
1. Inflated effective interval width: The computed credible interval width is multiplied by a conservatism factor
c>1 (controlled by the conservatism parameter, defaulting to 5) before comparison against the stopping
threshold. This inflation means that nominally narrow intervals no longer satisfy the stopping criterion,
requiring additional data collection.
11

<!-- Source page 12 -->
optstop
2. Tightened stabilisation threshold: The slope threshold for the stabilisation criterion is divided by the conser-
vatism factor (| ˆβ|<ϵ/c ), requiring more convincing evidence of plateau before stabilisation-based stopping is
permitted.
The effect of these adjustments is to delay stopping decisions for low-performing model-task combinations, providing
additional opportunity for rare successes to be observed. The conservatism adjustment is asymmetric: it applies only
when performance is poor, not when performance is high. A model that succeeds on 99% of attempts can be confidently
characterised with fewer observations than one that succeeds on 1% of attempts, reflecting the differential inferential
demands of these situations.
This asymmetry aligns with the pragmatics of capability evaluation. When assessing whether a model can perform a
task (capability detection), rare successes are highly informative; when assessing how well a model performs a task it
clearly can do (capability measurement), rare failures are less decision-relevant. The conservatism mechanism encodes
this asymmetry directly into the stopping rules. Note that conservatism and low_performance_threshold are
coupled parameters: for a given data budget, the effective CI-width target (δ/c) must remain achievable. With defaults
(c= 5 ,δ= 0.05 ), the effective target is 0.01 - achievable with moderate data. Appendix B.11 presents a dedicated
sensitivity analysis isolating the conservatism mechanism across calibrated performance levels.
A.2 Hierarchical Inference
LLM evaluation data possess a natural hierarchical structure: individual responses (observations) are nested within items
(distinct prompts or problems), which are themselves nested within evaluation groupings (model-task combinations).
This structure motivates a hierarchical approach to inference and stopping decisions, operating simultaneously at
multiple levels of aggregation.
At the item level, the unit of analysis is a single evaluation item (e.g., one mathematical problem or one coding
challenge) assessed across multiple epochs - repeated evaluations of the same item, potentially with varied sampling
parameters or random seeds. The inferential goal at this level is to characterise model performance on that specific
item with adequate precision. When the credible interval for an item’s success rate (or score distribution) becomes
sufficiently narrow, further epochs for that item are unnecessary - the model’s behaviour on that particular input is
well-characterised.
At the grouping level, the unit of analysis is an aggregation of items sharing common characteristics - typically a specific
model evaluated on a specific task, though more granular groupings (e.g., by difficulty level or topic) are supported. The
inferential goal at this level is to characterise the model’s overall performance on the task, integrating information across
all constituent items. When the credible interval for the grouping’s aggregate performance becomes sufficiently narrow,
the evaluation of that model-task combination can terminate entirely, with remaining (unevaluated) items skipped.
This hierarchical structure yields a natural cascade of stopping decisions. Early in an evaluation run, item-level stopping
criteria begin to trigger for individual items where model behaviour is consistent across epochs. As item-level data
accumulates, grouping-level inference integrates these observations, and grouping-level stopping criteria may trigger
for model-task combinations where aggregate performance is well-characterised. The evaluation thus progressively
focuses computational resources on the most uncertain regions of the evaluation space: items with variable behaviour
and groupings with heterogeneous performance across items.
The optstop package implements this hierarchy through distinct but coordinated inference processes at each level.
Item-level inference operates on the epoch-wise observations for a single item, updating a posterior distribution over that
item’s performance parameter after each epoch. Grouping-level inference operates on summary statistics aggregated
across items, employing hierarchical Bayesian models that partially pool information across items while respecting
their individual characteristics.
The hierarchical Bayesian approach offers particular advantages for grouping-level inference. Consider estimating an
LLM’s overall success probability on a task comprising 100 distinct items. A naive approach might simply pool all
observations; treating successes and failures as exchangeable draws from a single Bernoulli distribution. However, this
ignores meaningful variation across items: some problems are inherently easier than others, and model performance
varies accordingly. At the opposite extreme, treating each item’s success probability as entirely independent discards
the commonality that they all represent the same model’s capability on related problems.
Hierarchical models navigate between these extremes through partial pooling. Item-level parameters are modelled as
draws from a population distribution whose parameters are themselves estimated from the data. Items with limited
observations are “shrunk” toward the population mean, borrowing strength from other items; items with extensive
observations retain estimates closer to their individual data. This approach yields more stable grouping-level estimates
than either complete pooling or no pooling, particularly when item sample sizes are uneven - as they inevitably become
12

<!-- Source page 13 -->
optstop
under adaptive stopping, where easy items terminate quickly and difficult items accumulate more observations. For
example, a mathematical reasoning task might include both routine calculations (high success probability) and complex
proofs (low success probability); hierarchical inference appropriately weights these when characterising overall task
performance.
A.3 Leveraging Groupings
The effectiveness of any optimal stopping procedure depends critically on the definition of the units across which
stopping decisions operate. In LLM evaluation, this choice is far from trivial: the “jagged frontier” of model capabilities
[13] - a metaphor borrowed from the study of AI-augmented professional tasks - means that performance varies
dramatically across tasks, domains, prompt formulations, and even superficial features of evaluation items. A model
that excels at arithmetic may struggle with algebra; one that handles formal English may falter with colloquial text.
Aggregating across these dimensions risks masking important heterogeneity, while disaggregating too finely may yield
sample sizes too small for reliable inference.
The optstop package addresses this through flexible, user-defined groupings - partitions of the evaluation space within
which stopping decisions operate independently. Each grouping maintains its own inference state, accumulates its
own observations, and triggers stopping criteria according to its own precision trajectory. When a grouping’s credible
interval achieves the required precision, evaluation of that grouping terminates while other groupings continue.
Groupings can be defined along any dimension captured in the evaluation metadata. A general rule of thumb is to use a
factorial design based on all manipulated factors that may systematically impact performance. Common configurations
include (but are not limited to):
• Model× Task: Each model-task combination constitutes a separate grouping, appropriate when the primary
goal is to characterise each model’s performance on each task independently.
• Model× Task× Difficulty: Further stratification by difficulty level or sub-task category, useful when capability
variation within tasks is substantial.
• Tag-based: Groupings defined by evaluation tags (e.g., “safety-critical”, “reasoning”, “factual-recall”), enabling
domain-specific stopping thresholds and conservatism settings.
The choice of grouping structure involves trade-offs between inferential resolution and statistical power. Finer groupings
provide more granular capability characterisation but require more observations per grouping to achieve precision
thresholds; coarser groupings achieve precision more quickly but may obscure important heterogeneity. These trade-offs
interact with the conservatism considerations discussed in Appendix A.1.3: groupings exhibiting low performance will
accumulate additional observations under the conservatism adjustment, naturally directing computational resources
toward capability boundaries where uncertainty is highest.
The grouping structure determines not only where stopping decisions are made but also what those decisions mean. A
stopping decision for a fine-grained grouping (e.g., “GPT-4 on multi-step arithmetic with chain-of-thought prompting”)
provides a precise capability statement about a specific configuration. A stopping decision for a coarse grouping (e.g.,
“GPT-4 on mathematical reasoning”) provides a broader but potentially less actionable summary. Evaluators should select
grouping structures that align with the decisions their evaluation is intended to inform. The independence of grouping-
level inference also provides natural parallelism in the evaluation process. As different groupings reach stopping criteria
at different times, the evaluation scheduler in inspect_ai implementations can redistribute computational resources
to remaining groupings. The evaluation thus progressively concentrates effort on the most uncertain regions of the
capability space, where additional observations provide the greatest inferential value.
A.4 Inference Pathways
Evaluation scores in LLM assessment take diverse forms. Some tasks yield binary outcomes - the model either produces
the correct answer or it does not (or is classified as such via a threshold). Others employ rubric-based scoring, where
human or model judges assign discrete ratings (e.g., 1–5 quality scores or 0–10 capability assessments). Still others
produce continuous metrics, such as BLEU scores, embedding similarities, or calibrated probability estimates. A
general-purpose stopping framework must accommodate this diversity, routing each score type to appropriate inferential
machinery while presenting a unified interface to the evaluator.
The package implements inference pathway routing based on user configuration and score context. Routing is determined
by user-specified parameters - ordinal_tasks substring patterns for ordinal scored tasks, and for continuous tasks,
continuous_tasks substring patterns (standalone mode), and the score_agg aggregation setting (via inspect_ai
integration) - with binary inference as the default. This routing proceeds according to the following rules:
13

<!-- Source page 14 -->
optstop
• Binary pathway: The default, engaged when no ordinal or continuous configuration matches the grouping.
• Ordinal pathway: Engaged when the grouping name matches a user-provided ordinal_tasks substring
pattern and scores are not aggregated.
• Bounded continuous pathway: Engaged when a score aggregation function (mean, median) is applied
(score_agg, via the inspect_ai integration), or when the grouping name matches a continuous_tasks
substring pattern (standalone mode).
The routing decision is made at the grouping level and persists throughout the evaluation. Because routing depends on
configuration parameters rather than observed score values, users with non-binary scoring schemes must declare these;
otherwise all groupings default to binary inference regardless of the actual score distribution.
Each pathway implements the same conceptual framework - Bayesian inference yielding credible intervals evaluated
against precision thresholds - but with distributional assumptions and model structures appropriate to the data type. The
following subsections detail these pathway-specific implementations.
A.4.1 Binary
Binary scoring represents the most common evaluation paradigm: the model’s response is judged correct (1) or incorrect
(0), with no intermediate gradations. Tasks employing exact-match evaluation, binary classifiers, or pass/fail rubrics
generate binary scores. The inferential goal is to estimate the underlying success probabilityθ∈[0,1] with adequate
precision.
Identification.The binary pathway is the default inference mode. Score type is determined once per grouping at
initialisation and does not change during the evaluation.
Item-Level Inference.For a single evaluation item assessed across multiple epochs, let s denote the number of
successes (score = 1) and n the total number of trials observed. The optstop package employs an adaptive data-
dependent prior where the prior distribution adjusts based on accumulating within-item evidence.
The prior parameters are set proportional to the current point estimate ˆp=s/n, with influence that decays exponentially
as sample size increases:
αprior = max (γ·ˆp,0.5), β prior = max (γ·(1−ˆp),0.5)
whereγ=b·exp(−n/10) is a scaling factor that diminishes with sample size, and b is a base strength parameter
(default 2). The floor of 0.5 corresponds to the Jeffreys non-informative prior, preventing the adaptive component
from producing weaker regularisation than this baseline. This formulation ensures that the prior exerts meaningful
regularisation with small samples but becomes increasingly dominated by likelihood as evidence accumulates - a
form of vanishing prior influence. Note that because the prior parameters depend on the observed data, this is not a
prior in the strict Bayesian sense; the construction is better understood as an empirical Bayes regularisation device.
The Stopping Rule Principle (Appendix A.1) strictly applies to models with fixed priors - a condition satisfied by
the grouping-level hierarchical models (Appendix A.4.1, Grouping-Level Inference) but not by this data-dependent
item-level construction. The item-level procedure is better justified by the vanishing influence of the adaptive prior:
becauseγ decays exponentially withn, the posterior is increasingly determined by the likelihood alone, and by the time
an item’s CI is narrow enough to trigger stopping, the prior’s contribution is negligible. The consequential stopping
decisions - at the grouping level - rest on standard hierarchical posteriors to which the SRP applies without qualification.
The posterior distribution is then:
θitem∼Beta(α prior +s,β prior + (n−s))
Credible intervals are computed via Monte Carlo sampling from this posterior, with equal-tailed quantiles extracted at
the desired credibility level (in contrast to the highest density intervals used at the grouping level; see Appendix A.1.1).
When conservatism is active (estimated performance below the low_performance_threshold; see Appendix A.1.3),
the prior is modified: the decay rate slows to γ=b·exp(−n/(10c)) wherec >1 is the conservatism parameter
(defaultc= 5 ), and the data-dependent component ofαprior is multiplied byc before the floor is applied. Under default
parameterisation, this multiplicative boost is absorbed by the max(·,0.5) floor when ˆpis very small, so the dominant
item-level conservatism effects are the slowed prior decay and the CI width inflation: the effective CI width is multiplied
bycbefore comparison against stopping thresholds.
Grouping-Level Inference.At the grouping level, observations are aggregated across items using a hierarchical
model with logit-normal structure. Leti= 1,...,N index the items within the grouping, withsi successes observed
acrossni epochs for itemi. The hierarchical model takes the form:
µgroup∼Normal(µ 0,σ 0)
14

<!-- Source page 15 -->
optstop
σgroup∼Exponential(λ)
zi∼Normal(0,1)
ηi =µ group +σ group·zi
θi =logit −1(clip(ηi,−6,6))(numerical stability safeguard, boundingθ i∈[0.0025,0.9975])
si∼Binomial(n i,θi)
where the default prior hyperparameters areµ0 = 0,σ0 = 1.5, andλ= 1.0 . The zero-centred prior mean on the logit
scale (µ0 = 0, corresponding to 50% prior expected success rate) provides a weakly informative default that does
not favour high or low performance, placing approximately 95% of prior mass on success probabilities between 0.05
and 0.95. Users may adjust this via the prior_mu parameter: when re-evaluating a model on a benchmark for which
previous results are available, settingµ0 to the logit of the known performance level (e.g., logit(0.75)≈1.1 ) improves
the accuracy of early point estimates and credible interval placement by centring the posterior near the true value from
the outset. Because credible intervals are computed on the probability scale via the logistic transform, a well-placed
posterior also yields narrower intervals than one centred near 50% at the same precision level, which can lead to
earlier stopping - though the magnitude of this effect depends on how far true performance is from the uninformed
mid-point, and how well the prior maps onto it. The default prior width ( σ0 = 1.5; adjustable via prior_sigma)
ensures that a mis-specified prior is overridden by data within a modest number of items (of order 10–20 under moderate
performance, though the exact rate depends on between-item heterogeneity and epochs per item), so the cost of an
incorrect assumption is bounded. This parameter governs only the grouping-level hierarchical prior; the item-level
adaptive prior (above) is unaffected.
Further,µgroup represents the population-level mean on the logit scale, andσgroup governs between-item heterogeneity.
The non-centred parameterisation (introducing auxiliary variableszi rather than samplingηi directly) facilitates efficient
MCMC sampling, particularly when between-item variance is small. The item-level success probabilitiesθi are obtained
by applying the inverse logit (sigmoid) transformation to the latent linear predictorηi.
The logit-normal hierarchical structure was selected over the conjugate Beta-Binomial alternative following controlled
simulation comparison (see Appendix B.6). Under a Beta-Binomial data generating process (inherently favouring that
model), the two approaches proved statistically indistinguishable in bias, coverage, and CI width across the mid-range
(0.1–0.9 true performance; bias ratio 1.00, CI width ratio 1.00, coverage 0.80 vs. 0.81). Near boundaries (0.05, 0.95)
the models remained closely matched. At exact boundaries (0.0 or 1.0) - where all items share identical success
probability and between-item heterogeneity is zero - both models exhibit zero nominal coverage, reflecting fundamental
information limitations when sparse binary data cannot distinguish true homogeneity from sampling coincidence. The
Beta-Binomial exhibited 120–9,206× more MCMC divergences than the logit-normal across conditions, with effective
sample sizes as low as 7 (vs consistently above 3,700 for the logit-normal), indicating substantially worse posterior
geometry. The logit-normal therefore provides equivalent estimation quality with dramatically better computational
reliability - the appropriate default for an adaptive framework where MCMC must run reliably across diverse and
unknown data regimes.
The population-level success probability (the primary target for grouping-level inference) is the expected group accuracy:
Θ = 1
N
PN
i=1θi, computed as the mean of item-level success probabilities across posterior draws. This correctly
accounts for between-item heterogeneity (σgroup); the simpler transformation logit−1(µgroup), which represents the
success probability of a typical item (zi = 0), can diverge from Θ when heterogeneity is large (by Jensen’s inequality).
Posterior inference proceeds via Markov Chain Monte Carlo sampling, yielding draws fromp(Θ|s i,ni). The credible
interval forΘprovides the basis for grouping-level stopping decisions.
Stopping Criteria.Both the CI width criterion and the stabilisation criterion (Appendix A.1.1–A.1.2) apply at item
and grouping levels. At the item level, Monte Carlo sampling from the adaptive Beta posterior permits rapid CI
computation without full MCMC machinery. At the grouping level, MCMC sampling is triggered at configurable
intervals to update the hierarchical posterior and evaluate stopping conditions. The CI width inflation and slope strictness
under conservatism (Appendix A.1.3) applies at the grouping level, multiplying the MCMC-derived CI width by c
before comparison againstdelta_cap, and dividing the slope thresholdCI_deltabyc, accordingly.
A.4.2 Ordinal (Discrete)
Many evaluation rubrics employ discrete ordered categories - quality ratings from 1–5, capability scores from 0–10, or
multi-level correctness assessments (incorrect / partially correct / fully correct). Such ordinal scores occupy a middle
ground between binary and continuous data: they preserve rank ordering (a score of 4 indicates better performance than
a score of 3) but do not necessarily imply equal intervals (the difference between 3 and 4 may not equal the difference
between 4 and 5 in any meaningful sense).
15

<!-- Source page 16 -->
optstop
This ordinal structure presents both opportunities and challenges for inference. Treating ordinal scores as continuous
(e.g., computing means) imposes interval-scale assumptions that may be unwarranted. Treating them as unordered
categories (multinomial models) discards the rank information. Appropriate inference requires models that respect
ordinality without assuming cardinality - a class of models well-developed in psychometrics and survey research [2].
Identification.The ordinal pathway is selected when the grouping name matches a user-provided ordinal_tasks
substring pattern (case-insensitive) and scores are not aggregated. The number of modelled categories is K=
ordinal_max_score+ 1 (default 11 for a 0–10 scale); ordinal_max_score should reflect the maximum possible
score for the rubric in use.
Item-Level Inference.Item-level inference for ordinal scores focuses on characterising the modal category - the most
probable score value - and the uncertainty surrounding this characterisation. The inferential target is the integer category
that represents typical performance, with the credible interval quantifying uncertainty about which category this is.
For a single item with observed scoresy1,...,y n acrossn epochs, a Bayesian bootstrap procedure [30] estimates the
posterior distribution over the modal category. The procedure operates as follows:
1. Draw Dirichlet-distributed weights over observations:w∼Dirichlet(1 n)
2. Construct a weighted histogram across categories using these weights
3. Identify the modal category asˆm= arg maxk(weighted count in categoryk)
4. Repeat forB= 10,000bootstrap samples of the modal category
The resulting distribution over modal categories ˆm(1),...,ˆm (B) is summarised via percentile credible intervals. This
CI is on the category scale - a CI of [6, 8] on a 0–10 scale indicates 97% posterior probability (at the default credibility
level) that the modal category lies between 6 and 8. For comparison against precision thresholds, the interval is
normalised to [0,1] by dividing by the maximum score value (K−1) . A sample-size-scaled floor prevents premature
stopping when bootstrap variance is zero due to homogeneous data:Wmin = 1/((K−1)· √n). This floor decreases
with sample size, reflecting that more agreeing observations genuinely warrant greater confidence.
Grouping-Level Inference.Grouping-level inference for ordinal data employs hierarchical models that partially pool
information across items while respecting ordinal structure. Theoptstoppackage implements two model variants:
Ordered Logistic (Cumulative Link) Model: This model, derived from the psychometric literature [25], posits a latent
continuous ability scale underlying the observed ordinal responses. The hierarchical structure places a population-level
distribution over item abilities using non-centred parameterisation:
µgroup∼Normal(µ 0,2)
σgroup∼Exponential(rate= 1)
zi∼Normal(0,1)
ηi =µ group +σ group·zi
The default prior standard deviation of 2 on the group mean (σ0 = 2; adjustable via prior_sigma) is wider than for
binary models (σ0 = 1.5), reflecting the broader latent scale for ordinal responses. The default µ0 = 0 is weakly
informative; users may adjust both parameters via prior_mu and prior_sigma (see Appendix A.4.1 for informed
prior guidance). For each latent abilityηi, the probability of observing categoryk or lower is given by a cumulative
logistic function:
P(Yi≤k) =logit −1(ck−ηi), k= 0,...,K−2
wherec0 <c 1 <···<c K−2 areK−1 ordered cutpoints partitioning the latent scale intoK categories. To ensure
identifiability, the first cutpoint is fixed at zero (c0 = 0), with subsequent cutpoints parameterised as cumulative sums of
positive increments:ck =Pk
j=1γj fork≥1 , whereγj =softplus(γ raw
j ) ensures positivity (K−2 free increments).
The raw incrementsγraw
j are given Normal priors whose mean and variance scale adaptively withK to ensure reasonable
cutpoint spacing across different rubric sizes. The category probabilities are then:
P(Yi =k) =P(Y i≤k)−P(Y i≤k−1)
with boundary conditions P(Yi≤−1) = 0 and P(Yi≤K−1) = 1 . Given aggregated category counts fi =
(fi,0,...,f i,K−1)for each itemi, the likelihood is multinomial:
fi∼Multinomial(n i,pi)
16

<!-- Source page 17 -->
optstop
where pi is the vector of category probabilities derived from the cumulative model. The population-level estimand is
the modal category of the item-averaged probability vector:ˆmgroup = arg maxk ¯pk, where¯pk = (1/N)PN
i=1pi,k.
Dirichlet-Multinomial Model: An alternative model treats ordinal categories as exchangeable (ignoring rank structure)
but introduces hierarchical pooling across items:
αgroup∼Dirichlet(1 K)
κ∼Gamma(shape= 2,rate= 0.1) (E[κ] = 20)
pi∼Dirichlet(κ·α group)
fi∼Multinomial(n i,pi)
This model is available as an alternative when ordered logistic assumptions are inappropriate (e.g., strongly bi-
modal response distributions that violate the latent-continuum assumption) or when MCMC sampling for the or-
dered logistic model encounters convergence difficulties. The population-level estimand for the Dirichlet model is
ˆmgroup = arg maxkαgroup,k, corresponding to the mode of the expected category distribution.
Note that in both such cases, the appropriate estimand for stopping decisions may not correspond to the evaluator’s
intended performance estimand (i.e., whilst modal categories are appropriate for stopping decisions, the evaluator may
still wish to report/use the mean across categories). This is not a problem (the evaluator can still calculate and use the
mean from the stopped data), but the two should not be confused in reporting.
Stopping Criteria (Hybrid Approach).Ordinal inference employs a hybrid stopping criterion addressing the
distinctive challenges of ordered categorical data. Two pathways to stopping are evaluated:
Pathway 1 (Modal CI with Entropy V alidation): The primary criterion evaluates modal credible interval width. However,
a narrow modal CI can arise spuriously when limited data happen to concentrate in one category, even though the true
distribution may be diffuse. To guard against such “false peaks,” Pathway 1 includes an entropy validation gate:
• Compute Shannon entropy of the estimated category distribution:H=− P
kpk log2pk (in bits)
• If modal CI width is below threshold BUT the posterior median entropy exceeds a peakedness threshold
(default 80% oflog 2Kbits), the narrow CI is deemed unreliable and stopping is not triggered
• Stopping via Pathway 1 requires both narrow modal CI AND low entropy, confirming a genuinely peaked
distribution
Pathway 2 (Entropy Convergence): For distributions that are legitimately diffuse - spread across multiple categories
without a clear mode - the modal CI may never achieve narrow thresholds. Pathway 2 evaluates whether the entropy
credible interval width (on the [0,1] normalised entropy scale) has fallen below a convergence threshold (default
0.10, corresponding to±5% precision on the entropy scale). This requires at least three inference updates to guard
against unreliable early MCMC estimates. Unlike rate-of-change criteria, which may plateau before convergence
under exponential posterior contraction, this absolute-width criterion is satisfied in finite time under standard posterior
concentration, provided the model is well-specified and data are sufficiently informative.
This dual-pathway approach ensures appropriate stopping across diverse distributional shapes: peaked distributions
trigger Pathway 1; diffuse but converged distributions trigger Pathway 2; distributions still in flux (entropy CI still wide)
continue data collection.
A.4.3 Bounded Continuous
Some evaluation metrics yield continuous values within known bounds - embedding cosine similarities (after rescaling
to[0,1]), normalised BLEU scores in[0,1], or calibrated probability estimates. Additionally, when evaluators request
aggregation of discrete scores across sub-components (e.g., mean rubric scores across multiple criteria), the resulting
averages are effectively continuous on a bounded interval.
Identification.The bounded continuous pathway is selected when a score aggregation function ( score_agg: mean
or median) is applied via the inspect_ai integration, converting discrete sub-scores to continuous aggregates, or when
the grouping name matches a continuous_tasks substring pattern in standalone mode. Scores are normalised to the
unit interval[0,1]for inference, with results transformed back to the original scale for reporting.
17

<!-- Source page 18 -->
optstop
Item-Level Inference.For continuous bounded scores, item-level inference employs a Beta distribution model after
normalisation to [0,1] . Lety1,...,y n denote then observed scores for an item, normalised to the unit interval. The
sample mean ¯yand variances2 inform Beta posterior parameters via method-of-moments estimation: Given sample
statistics, the posterior is approximated as:
θitem∼Beta(α post,β post)
whereαpost andβpost are derived from moment-matching to the observed data, incorporating prior regularisation that
decays with sample size (analogous to the binary case). Credible intervals are computed via Monte Carlo sampling
from this posterior. The CI width, returned in the original score scale, is normalised to [0,1] by dividing by the score
range(U−L)before comparison againstdelta_item.
Grouping-Level Inference.Grouping-level inference for continuous bounded scores employs a hierarchical model
that aggregates information across items while dramatically reducing computational cost (relative to ordinal equivalents).
Rather than modelling individual observations (which could number in the thousands), the model operates on item-level
summary statistics - specifically, the mean score for each item.
The hierarchical structure uses logit-normal parameterisation with non-centred form:
µgroup∼Normal(µ 0,σ 0)
σgroup∼Exponential(λ σ)
ϕgroup∼Gamma(shape=α ϕ,rate=β ϕ)
zi∼Normal(0,1)
µi =logit −1(clip(µgroup +σ group·zi,−6,6))
where the default prior hyperparameters areσ0 = 1.5,λσ = 1.0,αϕ = 2, andβϕ = 1.0. The default prior meanµ0 = 0
(corresponding to 50% on the probability scale) reflects a neutral prior expectation for continuous scores; bothµ0 and
σ0 are configurable via prior_mu and prior_sigma (see Appendix A.4.1). Here, µgroup is the population mean on the
logit scale,σgroup governs between-item heterogeneity, andϕgroup is a precision (concentration) parameter controlling
within-item variability. The item-level meansµi are on the probability scale [0,1] after inverse-logit transformation. To
allow heterogeneous precision across items, item-level precision parameters are modelled hierarchically:
zϕ,i∼Normal(0,1)
ϕi = exp(logϕ group + 0.5·z ϕ,i)
where the factor 0.5 is a fixed log-scale standard deviation governing item-level precision heterogeneity. The key
computational optimisation lies in the likelihood specification. By the Central Limit Theorem, sample means of bounded
continuous observations are approximately normally distributed. The model therefore places a Normal likelihood on
observed sample means¯yi rather than on individual observations:
¯yi∼Normal
 
µi,
s
˜µi(1−˜µi)
ϕi·ni
!
where ˜µi =clip(µ i,0.01,0.99) prevents degenerate variance at boundary values, andni is the number of observations
contributing to item i’s mean. This aggregated likelihood provides an approximately 20× speedup compared to
modelling individual observations. For example, in a grouping with 50 items each contributing 20 observations, 50
item-level likelihood evaluations replace 1,000 observation-level evaluations.
The population-level mean isM= 1
N
PN
i=1µi, computed as the mean of item-level means across posterior draws (the
same estimand construction as for binary inference; see Appendix A.4.1). Posterior inference proceeds via MCMC
sampling, with the credible interval forM providing the basis for stopping decisions. The normalised CI width (on the
[0,1] scale) is compared directly against the precision threshold delta_cap; original-scale bounds (multiplied by the
range[upper bound−lower bound]) are reported in metadata for interpretability.
Stopping Criteria.Both CI width and stabilisation criteria apply to bounded continuous scores, operating on the
normalised scale for consistency. The conservatism adjustment (Appendix A.1.3) is applied based on normalised
performance: a grouping with normalised mean score below 1% (the default low_performance_threshold) triggers
conservative stopping behaviour. The normalised CI width is multiplied byc before comparison against delta_cap, and
the stabilisation slope threshold is divided byc, both extending data collection to guard against premature conclusions
about near-floor performance.
18

<!-- Source page 19 -->
optstop
A.5 Worked Illustration
To illustrate the framework specifications in Appendix A.1–A.4, we present a hypothetical worked example ofoptstop
operating within a representative evaluation scenario. The following traces expected behaviour based on the statistical
properties described in the preceding appendix subsections; empirical validation with real data appears in Section 3.
A.5.1 Evaluation Setup
Consider an evaluation assessing two language models - Model A (strong performer) and Model B (weak performer,
below 1% accuracy on Task 1) - on two distinct tasks:
• Task 1 (Binary): A factual question-answering task scored as correct (1) or incorrect (0)
• Task 2 (Ordinal): A reasoning quality assessment scored on a 0–10 rubric 2
The ordinal groupings assume hybrid inference mode ( ordinal_inference=’hybrid’, the default when using
the package via inspect_ai; standalone mode defaults to ’modal’), which includes both modal CI and entropy
convergence pathways. This configuration yields four groupings, each analysed independently (Table 2):
Table 2: Model groupings, tasks, and assumed performance characteristics
Grouping Model Task Assumed Pattern
G1 Model A Task 1 (Binary) High accuracy, consistent
G2 Model A Task 2 (Ordinal) Scores clustered in upper range
G3 Model B Task 1 (Binary) Low accuracy, conservatism active
G4 Model B Task 2 (Ordinal) Low, diffuse score distribution
Each task comprises 200 items, with up to 10 epochs permitted per item. A complete evaluation without early stopping
would require 8,000 trials (2 models×2 tasks×200 items×10 epochs).
A.5.2 Model A: Strong Performer
Grouping G1 (Binary Task):Model A’s high accuracy yields consistent success patterns across items. At the item
level, items with uniform outcomes (consistent successes) achieve narrow credible intervals quickly, as the item-level
Beta posterior (Appendix A.4.1) concentrates near its upper bound. Occasional items with mixed outcomes take
somewhat longer, since the posterior spans a wider range of plausible success rates.
At the grouping level, the hierarchical model rapidly accumulates evidence for a high mean success probability across
items. As items contribute data, the posterior concentrates and the credible interval narrows; grouping-level precision is
reassessed at discrete intervals (everyXmany completed trials, whereXis set by the user via reanalysis_interval).
Once the grouping-level precision threshold is met, evaluation of G1 terminates - remaining items need not be evaluated,
and incomplete items can be discontinued.
Grouping G2 (Ordinal Task):Model A’s scores cluster in the upper range of the rubric (e.g., predominantly 7–9),
representing a peaked distribution. At the item level, items with consistent scoring achieve narrow modal credible
intervals relatively quickly, as the Bayesian bootstrap concentrates on a clear modal category.
At the grouping level, Pathway 1 (modal CI with entropy validation) governs stopping. This requires two conditions to
be satisfied independently: the hierarchical modal CI must be narrow (below delta_cap), and a separate entropy check
must confirm that posterior median entropy falls below the peakedness threshold (Appendix A.4.2; default 80% of
log2K bits) - confirming genuine distributional concentration rather than a spurious peak from limited data. Grouping
G2 typically achieves substantial efficiency gains: when scores cluster in a narrow range of the rubric, both conditions
can be satisfied simultaneously with relatively few observations.
A.5.3 Model B: Weak Performer
Grouping G3 (Binary Task):Model B’s low accuracy triggers the conservatism regime. At the item level, two
mechanisms collectively delay stopping decisions: effective CI widths are inflated by the conservatism factorc (default
5) before comparison against thresholds, and adaptive prior decay slows five-fold (the prior retains influence over more
2Continuous scores (Appendix A.4.3) are also supported but omitted here for brevity.
19

<!-- Source page 20 -->
[RESULTS REDACTED: Appendix B empirical validation, numerical summaries, figures, and result-bearing discussion]

<!-- Source page 21 -->
[RESULTS REDACTED: Appendix B empirical validation, numerical summaries, figures, and result-bearing discussion]

<!-- Source page 22 -->
[RESULTS REDACTED: Appendix B empirical validation, numerical summaries, figures, and result-bearing discussion]

<!-- Source page 23 -->
[RESULTS REDACTED: Appendix B empirical validation, numerical summaries, figures, and result-bearing discussion]

<!-- Source page 24 -->
[RESULTS REDACTED: Appendix B empirical validation, numerical summaries, figures, and result-bearing discussion]

<!-- Source page 25 -->
[RESULTS REDACTED: Appendix B empirical validation, numerical summaries, figures, and result-bearing discussion]

<!-- Source page 26 -->
[RESULTS REDACTED: Appendix B empirical validation, numerical summaries, figures, and result-bearing discussion]

<!-- Source page 27 -->
[RESULTS REDACTED: Appendix B empirical validation, numerical summaries, figures, and result-bearing discussion]

<!-- Source page 28 -->
[RESULTS REDACTED: Appendix B empirical validation, numerical summaries, figures, and result-bearing discussion]

<!-- Source page 29 -->
[RESULTS REDACTED: Appendix B empirical validation, numerical summaries, figures, and result-bearing discussion]

<!-- Source page 30 -->
[RESULTS REDACTED: Appendix B empirical validation, numerical summaries, figures, and result-bearing discussion]

<!-- Source page 31 -->
[RESULTS REDACTED: Appendix B empirical validation, numerical summaries, figures, and result-bearing discussion]

<!-- Source page 32 -->
[RESULTS REDACTED: Appendix B empirical validation, numerical summaries, figures, and result-bearing discussion]
