---
title: Statistics
description: Validation statistics used by the Lab - formulas, when to use each, and citations.
---

# Statistics

<p class="nv-lede">The statistical toolkit behind the Hypothesis Lab and the research engine. Everything is plain
numpy/scipy and deterministic for a given seed. Sources: <code>ml-engine/lab/stats.py</code> (new in the Lab) and
<code>ml-engine/research/validation/metrics.py</code> (reused, not reimplemented).</p>

!!! tip "Which test should I use?"
    | Question | Use |
    |---|---|
    | Is this one IC series different from zero? | [HAC *t*](#hac-t-statistic) + [block bootstrap CI](#bootstrap-confidence-intervals) |
    | Does my score beat a baseline? | [Paired IC test](#paired-ic-test) / incremental IC |
    | I tried many ideas: which survive? | [Holm](#holm-step-down), [Romano–Wolf](#romanowolf-step-down), [DSR](#deflated-sharpe-ratio), [PBO](#probability-of-backtest-overfitting-cscv) |
    | Does the *best* of many strategies beat the benchmark? | [White RC](#whites-reality-check) / [Hansen SPA](#hansen-spa) |
    | How should I cross-validate with overlapping labels? | [Purged k-fold / CPCV](#purged-cross-validation) |
    | Are predicted probabilities honest? | [Brier, reliability, ECE](#calibration) |

## Correlation and *t*-statistics

### Rank IC

The Spearman correlation between the score and the forward return, computed per date. In
`research/validation` a date gets NaN if it has fewer than `min_names` complete pairs.

### HAC t-statistic

Overlapping \(h\)-session labels make a daily IC series autocorrelated up to lag \(h-1\). So
`hac_t` divides the mean by a long-run variance:

\[
t_{\text{HAC}} = \frac{\bar x}{\sqrt{\widehat{\text{LRV}}/T}},\qquad
\widehat{\text{LRV}}_{\text{HH}} = \hat\gamma_0 + 2\sum_{k=1}^{h-1}\hat\gamma_k
\]

The Hansen–Hodrick (uniform kernel) estimate is used first. If it is \(\le 0\), the code falls back to
Newey–West/Bartlett with \(L = 4h\): \(\hat\gamma_0 + 2\sum_{k=1}^{L}(1 - \tfrac{k}{L+1})\hat\gamma_k\).
The Hypothesis Lab rebalances without overlap, so it calls `hac_t(x, 1)`, which reduces to the plain *t*.
*Hansen & Hodrick (1980); Newey & West (1987).*

### t\*

`t_star` = min(HAC *t* on the daily series, the median over offsets of the plain *t* on every \(h\)-th
observation). This is a conservative choice for overlapping labels.

### Paired IC test

The HAC *t* of the per-date IC difference between the model and a baseline, on common dates.
The Hypothesis Lab uses it to compare against each baseline.

## Bootstrap confidence intervals

=== "Circular block bootstrap"

    `research/validation`: blocks of fixed length wrap around the end of the series. The default
    block is \(2h\) for daily series and 3 for monthly series, with 2,000 replications, seed
    20261010 and percentile intervals. The Hypothesis Lab uses block \(\max(2, \mathrm{round}(T^{1/3}))\).

=== "Stationary bootstrap"

    `lab/stats.py`: block lengths are geometric with mean `mean_block`, wrapping circularly. A new
    block starts with probability \(1/\text{mean\_block}\) at each step. This is the resampling
    used by White RC, SPA and Romano–Wolf. *Politis & Romano (1994).*

## Multiple testing

### Holm step-down

\[
\tilde p_{(i)} = \min\!\Big(1,\ \max_{j \le i}\,(m - j + 1)\,p_{(j)}\Big)
\]

Controls the FWER under any dependence. Use it for a few candidates whose individual *p*-values you already have. *Holm (1979).*

### Benjamini–Hochberg and Benjamini–Yekutieli

\[
\tilde p_{(i)}^{\text{BH}} = \min_{j \ge i} \frac{m\,p_{(j)}}{j},\qquad
\tilde p^{\text{BY}} = \text{BH}\big(c(m)\,p\big),\ c(m) = \sum_{i=1}^m \tfrac1i
\]

These control the FDR, so use them when screening many features and some false positives are
acceptable. BY is valid under arbitrary dependence. *Benjamini & Hochberg (1995); Benjamini & Yekutieli (2001).*

## Data-snooping tests

All three take a \(T \times M\) matrix of excess returns (strategy minus benchmark) and use the stationary bootstrap.

### White's Reality Check

\[
V = \max_k \sqrt{T}\,\bar d_k,\qquad V^* = \max_k \sqrt{T}\,(\bar d^*_k - \bar d_k),\qquad p = \Pr(V^* \ge V)
\]

Tests H₀: no strategy beats the benchmark. It uses the least-favourable recentring, so many poor
strategies make it conservative. *White (2000).*

### Hansen SPA

A studentised version with \(\omega_k\) = the bootstrap s.d. of \(\sqrt{T}\bar d^*_k\). Strategies
with \(\sqrt T\bar d_k/\omega_k < -\sqrt{2\log\log T}\) keep their negative mean in the bootstrap, so
clearly bad strategies no longer dilute the test. This gives the consistent *p*-value. *Hansen (2005).*

### Romano–Wolf step-down

Gives an adjusted *p*-value for **each** strategy (H₀ₖ: mean ≤ 0). Studentised statistics are taken in
descending order, and step \(j\) compares \(t_{(j)}\) with the bootstrap maximum over the strategies
not yet rejected. The *p*-values are made monotone. It controls the FWER while using the correlation
between strategies. Used by [compare](hypothesis-lab.md#comparing-candidates). *Romano & Wolf (2005).*

## Overfitting

### Deflated Sharpe ratio

\[
SR_0 = \sqrt{V}\Big[(1-\gamma)\,\Phi^{-1}\!\big(1-\tfrac1N\big)+\gamma\,\Phi^{-1}\!\big(1-\tfrac{1}{Ne}\big)\Big],\quad
\text{DSR} = \Phi\!\left(\frac{(\widehat{SR}-SR_0)\sqrt{T-1}}{\sqrt{1-\gamma_3\widehat{SR}+\frac{\gamma_4-1}{4}\widehat{SR}^2}}\right)
\]

This is the probability that the true Sharpe ratio exceeds the best you would expect from \(N\)
unskilled trials. \(V\) is the variance of the Sharpe ratios across trials (the Lab uses \(1/T\)),
and \(\gamma_4\) is the non-excess kurtosis. The research engine's `dsr()` works in monthly units and
puts a floor under \(N\). **Always log the trial count.** *Bailey & López de Prado (2014).*

### Probabilistic Sharpe ratio

The same formula with any benchmark \(SR^*\) in place of \(SR_0\). *Bailey & López de Prado (2012).*

### Minimum backtest length

\[
\text{MinBTL} \approx \left(\frac{\mathbb E[\max_N Z]}{SR_{\text{target}}}\right)^{2}\ \text{years}
\]

This estimates how many years of data are needed before the best of \(N\) trials reaching an
annualised \(SR_{\text{target}}\) is not just luck. It is 0 for a single trial. *Bailey, Borwein, López de Prado & Zhu (2014).*

### Probability of backtest overfitting (CSCV)

The \(T \times N\) performance matrix is split into \(s\) blocks (default 16). For every one of the
\(\binom{s}{s/2}\) ways to choose half the blocks as in-sample, take the in-sample-best trial by
Sharpe and find its out-of-sample relative rank \(\omega\):

\[
\text{PBO} = \Pr\!\big[\operatorname{logit}(\omega) \le 0\big],\qquad \omega = \frac{\text{rank}}{N+1}
\]

A high PBO means the in-sample winner typically ends up in the bottom half out of sample. *Bailey, Borwein, López de Prado & Zhu (2017).*

### Sharpe CI (Mertens)

\[
\widehat{\text{SE}}(\widehat{SR}) = \sqrt{\frac{1-\gamma_3\widehat{SR}+\frac{\gamma_4-1}{4}\widehat{SR}^2}{T-1}}\times\sqrt{\text{periods/yr}}
\]

For normal returns this reduces to Lo's \(\sqrt{(1+SR^2/2)/T}\). Annualising assumes iid returns. *Mertens (2002); Lo (2002).*

## Purged cross-validation

=== "Purged k-fold"

    The data is split into \(k\) contiguous test blocks. Row \(i\)'s label spans \([i, i+h]\), so a
    training row is **purged** if \(i \in [\text{start}-h,\ \text{end}]\). An **embargo** also drops
    \((\text{end}, \text{end}+e]\). *López de Prado (2018), AFML ch. 7.*

=== "CPCV"

    Every \(\binom{N}{k}\) choice of \(k\) test groups, each purged and embargoed separately, so
    training data can sit between test groups. It gives \(\varphi = \tfrac{k}{N}\binom{N}{k}\)
    backtest paths. *López de Prado (2018), AFML ch. 12.*

## Calibration

| Method | Formula / rule | Citation |
|---|---|---|
| Brier score | \(\frac1n\sum (p_i - y_i)^2\) | Brier (1950) |
| Brier skill score | \(1 - \text{Brier}(p)/\text{Brier}(\text{ex-ante base rate})\) | — |
| Log loss | \(-\frac1n\sum y\log p + (1-y)\log(1-p)\), with \(p\) clipped to \([10^{-15}, 1-10^{-15}]\) | — |
| AUC | Tie-aware Mann–Whitney, optional weights | — |
| Reliability diagram | Quantile or uniform bins with **Wilson** CIs, plus ECE and MCE | Naeini, Cooper & Hauskrecht (2015); Wilson (1927) |
| Wilson interval | \(\dfrac{\hat p + \frac{z^2}{2n} \pm z\sqrt{\frac{\hat p(1-\hat p)}{n}+\frac{z^2}{4n^2}}}{1+z^2/n}\) | Wilson (1927) |

## Intervals and quantiles

| Method | Rule | Citation |
|---|---|---|
| Split-conformal half-width | The \(\lceil (n+1)(1-\alpha)\rceil\)-th smallest \(\lvert r\rvert\); \(\infty\) if that rank exceeds \(n\) | Vovk et al. (2005); Lei et al. (2018) |
| Pinball loss | \(\rho_\tau(u) = \max(\tau u, (\tau-1)u)\), averaged over rows and quantile levels | Koenker & Bassett (1978) |
| Interval score | \((h-l) + \tfrac{2}{\alpha}(l-y)\mathbb 1_{y<l} + \tfrac{2}{\alpha}(y-h)\mathbb 1_{y>h}\) | Gneiting & Raftery (2007) |

Full references with DOIs are in the [Literature review §5](research/literature.md#5-backtest-overfitting-and-multiple-testing-controls).
