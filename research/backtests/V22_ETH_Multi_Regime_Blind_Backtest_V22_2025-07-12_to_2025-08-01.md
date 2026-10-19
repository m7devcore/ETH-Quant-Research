# ETH V22 Multi-Regime Blind Backtest Report

> **Public Release Note:** This document is a privacy-redacted copy of the original internal research report. Identifying personal names in section titles have been replaced with standard executive headings (e.g. Executive Summary). All numerical backtest results, dates, trade metrics, and methodology remain 100% unaltered.

## Multi-Regime Training → Adaptation → Fresh Test
## Asset: ETHUSDT Futures
## Venue: Binance Futures
## Timezone: Europe/Istanbul

---

# 1. Objective

V22 was created after V21 exposed a critical methodological failure:

A model can pass chronological walk-forward validation inside one 14-day regime and still fail badly when the data-generating regime changes.

V21 official Hidden:
**85/187 = 45.45%**

V22 therefore changed the training architecture.

Instead of:

`one Study regime → one model → Hidden`

V22 uses:

# `multi-regime research corpus → multiple experts → state permission → fresh untouched test`

The goal is not to maximize a single-period score.

The goal is to learn a mapping that remains useful across materially different historical regimes.

---

# 2. Test Environments

V22 explicitly separates three environments.

## Environment A — Research / Training

Previously seen V1–V21 history is allowed for:
- feature learning,
- model training,
- model architecture selection,
- regime diversity.

It is NOT considered fresh validation.

For the numerical multi-regime model, V22 used 18 complete historical Study windows:

- V4–V9
- V10–V15
- V16–V21

V1–V3 remain part of the qualitative learning corpus and methodology.

---

## Environment B — Adaptation / Preflight

Dates:

**12 Jul 2025 → 25 Jul 2025**

Purpose:

- choose how already-trained experts are combined,
- test confidence/consensus permission,
- test temporal stability,
- no expert retraining.

This period is not the final test.

---

## Environment C — Fresh Test

Dates:

# **26 Jul 2025 → 1 Aug 2025**

This block remained unopened until:
- all experts were trained,
- ensemble method was selected,
- confidence threshold was selected,
- expert-disagreement threshold was selected,
- training-distance permission was selected.

No training or tuning was performed after the Fresh Test was opened.

---

# 3. Why V22 Exists

V21 showed:

- Study walk-forward: 60.66%
- Hidden: 45.45%
- model collapsed to bullish prior
- model accuracy equaled always-UP
- class balancing did not fix it
- intercept removal did not fix it
- simple OOD filtering did not fix it
- naive online updates did not fix it

The V22 hypothesis:

> A single model trained on one regime cannot learn stable next-candle behavior. Train multiple experts on multiple historical regime groups and only trade when experts broadly agree and the current state is inside historical support.

---

# 4. Feature Set

All V22 experts use the same 18 features inherited from V21.

## Local return path

1. 1-bar return / ATR7
2. 3-bar return / ATR7
3. 6-bar return / ATR7
4. 12-bar return / ATR7

## Efficiency

5. ER6
6. ER12
7. ER24

## Candle structure

8. current 15m candle body / ATR7
9. current 15m candle range / ATR7

## Local volatility

10. ATR7 / price
11. ATR7 / ATR28

## Trend/value structure

12. EMA9 − EMA21 / ATR7
13. EMA21 4-bar slope / ATR7
14. 32-bar midpoint migration over 8 bars / ATR7
15. close − 32-bar midpoint / ATR7

## 4H context

16. 4H ER6
17. 4H close − EMA13 / 4H ATR14
18. 4H ATR7 / ATR28

No future candle information is included.

---

# 5. Expert Architecture

Three independent logistic experts were trained.

All experts use:

- 18 common features
- Study-only standardization for their own corpus
- L2 regularization = 0.20
- 260 gradient iterations
- learning rate = 0.04
- next 15m candle direction as label

## Expert A

Training regimes:

**V16–V21**

Approximately:

**7,455 labeled 15m examples**

This expert represents the most recent historical regime group.

---

## Expert B

Training regimes:

**V10–V15**

Approximately:

**7,452 examples**

This represents the middle historical regime group.

---

## Expert C

Training regimes:

**V4–V9**

Approximately:

**7,445 examples**

This represents the older historical regime group.

---

# 6. Leave-One-Period-Out Multi-Regime Validation

Before Adaptation, each group was tested using complete-period holdouts.

For every group:

- train on five full historical periods,
- hold out one complete period,
- repeat for every period.

This is much stricter than random candle splits.

The candidate confidence threshold was:

# `0.56`

---

# 7. V16–V21 Group

At threshold 0.56:

| Period | Signals | Accuracy |
|---|---:|---:|
| V16 | 52 | 55.77% |
| V17 | 82 | 56.10% |
| V18 | 79 | 56.96% |
| V19 | 31 | 58.06% |
| V20 | 58 | 58.62% |
| V21 | 82 | 64.63% |

Every period remained above approximately 55%.

This directly improves on V21's single-regime failure.

---

# 8. V10–V15 Group

At threshold 0.56:

| Period | Signals | Accuracy |
|---|---:|---:|
| V10 | 226 | 63.27% |
| V11 | 262 | 56.49% |
| V12 | 252 | 59.13% |
| V13 | 303 | 59.41% |
| V14 | 221 | 65.61% |
| V15 | 304 | 56.91% |

Again, every complete held-out period exceeded 56%.

---

# 9. V4–V9 Group

At threshold 0.56:

| Period | Signals | Accuracy |
|---|---:|---:|
| V4 | 143 | 60.14% |
| V5 | 86 | 66.28% |
| V6 | 121 | 57.85% |
| V7 | 174 | 55.75% |
| V8 | 99 | 61.62% |
| V9 | 158 | 53.80% |

V9 was the weakest full-period result but remained above 50%.

---

# 10. Aggregate Historical Multi-Regime Validation

Across all 18 complete held-out periods:

Signals:

# **2,733**

Hits:

# **1,619**

Aggregate accuracy:

# **59.24%**

Worst complete-period accuracy:

# **53.80%**

Average period accuracy:

approximately:

# **59.24%**

This is the first research result in the V1–V22 sequence that combines:

- thousands of signals,
- many historical regimes,
- complete-period holdouts,
- no tiny-sample perfection.

---

# 11. Why Threshold 0.56 Was Not Used Directly in Final Ensemble

The three experts are trained on different historical distributions.

A raw 0.56 probability from Expert A is not guaranteed to have identical calibration to 0.56 from Expert B or C.

V22 therefore did not simply vote on independently thresholded probabilities.

Instead, Adaptation was used to test how the expert outputs should be combined.

---

# 12. Adaptation Environment

Dates:

**12–25 Jul 2025**

The expert coefficients were frozen before this period.

Tested combination families:

1. simple probability average
2. 2-of-3 voting
3. 3-of-3 voting
4. nearest-distribution expert
5. inverse-distance weighted expert average
6. expert-agreement + training-support permission

No expert was retrained.

---

# 13. Simple Average

Best broad simple-average region:

`p_avg >= 0.55 → UP`

`p_avg <= 0.45 → DOWN`

Result:

- Signals: 236
- Hits: 132
- Accuracy: **55.93%**
- always-UP on same subset: **52.97%**
- average directional return: **+0.0207%**

But temporal stability was imperfect:

- first half: 50.85%
- second half: 61.02%

Therefore simple average alone was not frozen.

---

# 14. Nearest-Expert Routing

For every current state, V22 measured normalized feature distance from each expert's training distribution.

The closest expert was selected.

This did not improve temporal stability enough.

Conclusion:

# Simply selecting one nearest expert is not sufficient.

---

# 15. Expert Agreement as State Permission

V22 then used disagreement itself as information.

For the three expert probabilities:

`spread = max(p_A,p_B,p_C) - min(p_A,p_B,p_C)`

Interpretation:

- low spread = experts agree
- high spread = regime/model disagreement

V22 also calculated:

`minDist = minimum normalized RMS feature distance to any expert training distribution`

This creates explicit state permission:

> Trade only when expert consensus is high enough and current state is reasonably supported by historical training distributions.

---

# 16. OFFICIAL FROZEN V22 RULE

Frozen before Fresh Test.

## Expert output

`p_avg = (p_A + p_B + p_C) / 3`

## Confidence permission

If:

`p_avg >= 0.55`

predict:

**UP**

If:

`p_avg <= 0.45`

predict:

**DOWN**

Otherwise:

**NO TRADE**

---

## Expert agreement permission

Require:

# `expert probability spread <= 0.06`

Otherwise:

**NO TRADE**

---

## Historical support permission

Calculate normalized RMS feature distance to each expert's training distribution.

Require:

# `minimum expert distance <= 2.0`

Otherwise:

**NO TRADE**

---

## Horizon

Prediction target:

# next completed 15m candle direction

No retraining.

No online update.

No Hidden recalibration.

---

# 17. Official Adaptation Result

Final frozen V22 rule on Adaptation:

Signals:

# **159**

Hits:

# **95**

Accuracy:

# **59.75%**

Always-UP baseline:

# **52.83%**

Average directional close return:

# **+0.0419%**

Temporal stability:

- Early third: **56.25%**
- Middle third: **60.00%**
- Late third: **61.97%**
- First half: **59.15%**
- Second half: **60.23%**

This temporal stability was materially better than the simple ensemble.

---

# 18. Why This V22 Candidate Was Frozen

V22 did NOT freeze the mathematically highest Adaptation score.

Some smaller variants reached 61–63%.

They were rejected because:
- sample size was smaller,
- some segments became unstable,
- average directional return weakened,
- the threshold surface became more fragile.

The chosen rule was preferred because it showed a broad balance between:

- accuracy
- sample size
- temporal stability
- expert agreement
- distribution support

---

# 19. FRESH TEST MARKET

Dates:

**26 Jul → 1 Aug 2025**

15m candles:

**672**

Market:

- Open: **3683.58**
- Close: **3539.90**
- High: **3940.81**
- Low: **3490.00**
- Net: **-3.90%**

This was directionally different from several bullish training/adaptation regimes.

---

# 20. OFFICIAL V22 FRESH TEST RESULT

Signals:

# **81**

Hits:

# **48**

Misses:

# **33**

Accuracy:

# **59.26%**

Error:

# **40.74%**

Coverage:

# **12.05%**

This is the official untouched V22 result.

---

# 21. Direction Symmetry

## UP

Signals:

**41**

Accuracy:

# **58.54%**

Approximate hits:

**24**

## DOWN

Signals:

**40**

Accuracy:

# **60.00%**

Hits:

**24**

This is important.

V22 did not succeed by simply predicting the dominant market direction.

The direction split was almost perfectly balanced.

---

# 22. Baseline Comparison

Always-UP on the exact same selected Fresh Test candles:

# **49.38%**

V22:

# **59.26%**

Improvement over always-UP:

approximately:

# **+9.88 percentage points**

Unlike V21, V22 did not collapse to a directional prior.

---

# 23. Directional Return

Average signed next-candle close return in predicted direction:

# **+0.0635% per selected signal**

This is before:
- fees,
- spread,
- slippage,
- execution latency,
- risk sizing.

Therefore this is not yet a live profitability estimate.

---

# 24. Excursion Statistics

Average MFE:

# **0.2915%**

Average MAE:

# **0.3172%**

MAE remains slightly larger than MFE on average.

This means:

# directional classification improvement does not automatically establish a profitable trade implementation.

Execution/risk research remains necessary.

---

# 25. Daily Fresh Test Performance

| Date | Signals | Accuracy |
|---|---:|---:|
| Jul 26 | 10 | 70.00% |
| Jul 27 | 10 | 70.00% |
| Jul 28 | 9 | 55.56% |
| Jul 29 | 16 | 50.00% |
| Jul 30 | 12 | 66.67% |
| Jul 31 | 12 | 33.33% |
| Aug 1 | 12 | 75.00% |

Six of seven days were at or above 50%.

Jul 31 was the clear failure day.

This day should become an explicit V23 diagnostic target.

---

# 26. Largest Fresh Test Errors

Examples include:

## 1 Aug 16:45
Prediction: UP

Actual: DOWN

Directional close result:
**-0.724%**

MFE:
**0.093%**

MAE:
**1.365%**

---

## 30 Jul 17:45
Prediction: DOWN

Actual: UP

Directional close result:
**-0.639%**

MFE:
**0.120%**

MAE:
**0.986%**

---

## 30 Jul 22:00
Prediction: UP

Actual: DOWN

Directional close result:
**-0.587%**

MFE:
approximately zero

MAE:
**1.777%**

These prove that V22 still has severe individual direction failures.

The 59.26% result does not eliminate tail risk.

---

# 27. Strong Fresh Test Successes

Examples:

## 1 Aug 03:15
UP → UP

Directional close result:
**+0.870%**

MFE:
**1.126%**

MAE:
**0.052%**

## 30 Jul 18:00
DOWN → DOWN

Directional close result:
**+0.750%**

MFE:
**0.906%**

MAE:
**0.068%**

## 29 Jul 03:45
UP → UP

Directional close result:
**+0.685%**

These demonstrate that the model is capable of capturing meaningful directional candles on both sides.

---

# 28. The Most Important V22 Result

Three distinct evaluation levels produced almost the same result:

## Historical complete-period leave-one-out

# **59.24%**

## New Adaptation

# **59.75%**

## Completely Fresh Test

# **59.26%**

This is radically different from earlier versions such as:

- V18: very high percentage, tiny sample
- V20: Study 81.82% → Hidden 41.67%
- V21: Study walk-forward 60.66% → Hidden 45.45%

V22 did not collapse.

---

# 29. Statistical Caution

Fresh Test:

**48/81 = 59.26%**

The approximate 95% Wilson interval is roughly:

# **48.4% to 69.3%**

This interval still includes 50%.

Therefore V22 is:

# promising evidence

not:

# statistically proven edge

A larger number of untouched test periods is required.

---

# 30. What V22 Got Right

1. Used multi-regime training rather than one regime.
2. Treated old V1–V21 data as research/training only.
3. Validated using complete-period holdouts.
4. Used three independent historical expert groups.
5. Did not select the highest Adaptation percentage.
6. Used expert disagreement as a NO TRADE condition.
7. Used historical feature support as a NO TRADE condition.
8. Froze the complete rule before Fresh Test.
9. Achieved nearly identical accuracy across:
   - old regime holdouts,
   - adaptation,
   - fresh test.
10. Balanced UP and DOWN predictions in Fresh Test.
11. Beat always-UP materially on Fresh Test.
12. Produced positive average directional close return.

---

# 31. What V22 Still Gets Wrong

1. Fresh Test is only one week.
2. 81 signals is not enough to prove a durable statistical edge.
3. Jul 31 collapsed to 33.33%.
4. Several individual misses had very large adverse movement.
5. Average MAE remains slightly larger than MFE.
6. Classification accuracy has not been translated into executable PnL.
7. Fees/slippage are not included.
8. The three experts are grouped chronologically, not by fully learned regime clusters.
9. Probability calibration is not yet formally verified across fresh regimes.
10. V1–V3 are qualitative references rather than part of the numerical 18-window expert training.

---

# 32. V22 Research Score

# **88 / 100**

Why high:

- first genuinely multi-regime architecture,
- thousands of historical leave-one-period-out signals,
- full-period validation,
- clean adaptation/fresh separation,
- stable ~59% result across three different validation levels,
- balanced direction performance,
- no post-reveal repair.

Why not higher:

- only one Fresh Test week,
- interval still includes 50%,
- tail misses remain severe,
- execution profitability not established.

---

# 33. V22 Fragility Score

# **42 / 100**

This is materially lower fragility than V20/V21.

Reasons:

Positive:
- 18 historical held-out periods
- worst full-period training validation still above ~53.8%
- Adaptation and Fresh Test almost identical
- balanced UP/DOWN
- not dependent on one market direction

Remaining fragility:
- only one completely fresh week
- day-level failure still exists
- regime grouping remains coarse

---

# 34. Main Scientific Lesson

V21 taught:

> Walk-forward inside one regime is not enough.

V22 now provides the strongest evidence yet for:

# Multi-regime training + model disagreement + historical support permission.

The important improvement is NOT a magic threshold.

It is the training architecture.

Old method:

`one regime → learn mapping → hope it transfers`

V22:

`many regimes → independent experts → require agreement → require state support → predict / abstain`

---

# 35. V23 Primary Goal

Do NOT immediately change the V22 formula.

The first task of V23 should be:

# replicate V22 unchanged on another untouched complete period.

The best scientific test now is replication, not optimization.

---

# 36. V23 Pre-Registered Priorities

## Priority 1 — Replication

Use exact V22 frozen ensemble unchanged.

No retraining.

No new threshold.

Measure whether ~59% transports again.

---

## Priority 2 — Jul 31 failure diagnosis

Only after official replication is locked:

study the characteristics of bad-day clusters.

Do not add a day filter before fresh evidence.

---

## Priority 3 — Tail-risk model

Separate:

`Direction Model`

from:

`Adverse Excursion Risk Model`

The current directional classifier can be correct often while still exposing large MAE.

A later model should estimate:

- probability of large adverse excursion,
- expected MFE/MAE ratio,
- whether a correct directional thesis is economically tradeable.

---

## Priority 4 — Executable PnL backtest

Once direction replicates:

test:
- fees
- spread/slippage
- stop rules
- take-profit rules
- one-candle close exit
- risk sizing

Until this exists:

# 59.26% directional accuracy is not equivalent to 59.26% profitable trades.

---

# 37. V22 Final Conclusion

V22 is the first version in the sequence with a result that looks structurally different from earlier overfit successes.

Historical multi-regime LOO:

# 59.24%

Adaptation:

# 59.75%

Fresh untouched test:

# 59.26%

The consistency is the important result.

However:

- one fresh week is insufficient,
- statistical uncertainty still includes 50%,
- tail risk remains substantial.

Therefore:

# V22 is the strongest candidate so far, not a proven final trading system.

---

# 38. Short Executive Summary

V22 غيرنا طريقة التعلم بالكامل.

بدل ما ندرب على أسبوعين:
درّبنا 3 Experts على 18 فترة قديمة مختلفة.

بعدين كل فترة كاملة القديمة طلعت من التدريب لحالها واختبرنا عليها.

النتيجة التاريخية:
**59.24% على 2,733 إشارة**

بعدها استخدمنا 12–25 يوليو كـAdaptation فقط.

القانون النهائي صار:
- متوسط 3 Experts
- UP إذا المتوسط >=0.55
- DOWN إذا <=0.45
- لازم الخبراء يكونوا متفقين: spread <=0.06
- لازم الحالة قريبة من بيئة تدريب واحد منهم: distance <=2
- غير هيك NO TRADE

Adaptation:
**95/159 = 59.75%**

بعد ما جمدنا كل شيء فتحنا Fresh Test:
26 يوليو–1 أغسطس.

النتيجة:
**48/81 = 59.26%**

UP:
**58.54%**

DOWN:
**60%**

always-UP:
**49.38%**

وهذا أهم شيء:
التدريب القديم، الـAdaptation، والـFresh Test كلهم تقريبًا نفس الـ59%.

هاي أقوى علامة لحد الآن إن التعلم بدأ يعمم بدل ما يحفظ فترة واحدة.

لكن لسه ما بنقول لقينا edge نهائي.

بدنا V23 يكرر نفس V22 بدون تعديل على فترة جديدة untouched.
