# Literature review: models and evaluation methods for Nivesh

*Version 2026-10-19. Citations were checked against Crossref, arXiv, PMLR, AAAI OJS or the publisher's page on 2026-10-19 unless marked otherwise.*

**Context.** Nivesh works with **daily** data for Indian equities: OHLCV, delivery percentage and corporate actions. The data comes free from NSE and BSE files. It does **not** have survivorship-free fundamentals, intraday order books, or a licensed point-in-time constituent history (see [verified facts](verified-facts.md)). Each verdict below is judged against that constraint.

**Verdict key.**

- **Baseline:** build or use this now. It is the bar every new model must beat, or a test every result must pass.
- **Candidate:** worth a time-boxed experiment, but only after the baselines and the evaluation harness exist.
- **Not justified now:** the data, cost or evidence does not support it for daily Indian equities today.

!!! info "Summary"
    | Paper | Verdict |
    |---|---|
    | Gu, Kelly & Xiu 2020 | **Baseline** (method template) |
    | Chen, Pelger & Zhu 2024 | Not justified now |
    | Jiang, Kelly & Xiu 2023 / Murray, Xia & Xiao 2024 | **Candidate** |
    | MASTER (AAAI 2024) | Candidate |
    | StockMixer (AAAI 2024) | Candidate (low priority) |
    | Autoformer (NeurIPS 2021) | Not justified now |
    | Deep OFI (Kolm et al. 2023) | Not justified now |
    | TLOB (Berti & Kasneci 2025) | Not justified now |
    | Sirignano & Cont 2019 | Not justified now |
    | Chronos / TimesFM / Moirai | Candidate, **as a benchmark only** |
    | Deflated Sharpe Ratio | **Baseline** (required) |
    | Probability of Backtest Overfitting | **Baseline** (required) |
    | Harvey, Liu & Zhu 2016 | **Baseline** (required) |
    | White RC 2000 / Hansen SPA 2005 / Romano–Wolf 2005 | **Baseline** (required) |

---

## 1. Cross-sectional machine-learning asset pricing

### Gu, Kelly & Xiu, "Empirical Asset Pricing via Machine Learning"

- **Citation:** *Review of Financial Studies* 33(5): 2223–2273, 2020. [doi:10.1093/rfs/hhaa009](https://doi.org/10.1093/rfs/hhaa009). NBER WP 25398.
- **Does it exist?** Yes.
- **Claims:** The paper compares many ML methods for predicting monthly US stock returns from a large set of firm characteristics and macro predictors. Trees and neural networks do best, because they capture nonlinear interactions between predictors. Forecasts from these models give large economic gains, in some cases about double the performance of regression-based strategies. All methods agree that the strongest signals are variants of momentum, liquidity and volatility.
- **Code:** I found no official repository.
- **Applicability to India:** Partial. The full set of characteristics needs accounting data, which is not freely available point-in-time for India. However, the dominant signals (momentum, liquidity, volatility) can be built from daily OHLCV and delivery data, which Nivesh has. The method itself carries over directly: a pooled cross-sectional model, an expanding-window walk-forward split, and evaluation by out-of-sample R² and long-short decile portfolios.
- **Verdict: Baseline.** Use it as the template, not a replication: an elastic net plus a gradient-boosted tree on about 20 price, volume and delivery features, with walk-forward evaluation. Every fancier model has to beat this.

### Chen, Pelger & Zhu, "Deep Learning in Asset Pricing"

- **Citation:** *Management Science* 70(2): 714–750, 2024. [doi:10.1287/mnsc.2023.4695](https://doi.org/10.1287/mnsc.2023.4695). [arXiv:1904.00745](https://arxiv.org/abs/1904.00745).
- **Does it exist?** Yes.
- **Claims:** The authors estimate a stochastic discount factor with deep networks. Training uses the no-arbitrage condition as its objective, an adversarial network that builds the most informative test assets, and an RNN that extracts economic states from many macro series. Out of sample, the model beats all benchmarks on Sharpe ratio, explained variation and pricing errors.
- **Code:** The INFORMS page lists replication files, but I did not inspect them. A GitHub repository, [jasonzy121/Deep_Learning_Asset_Pricing](https://github.com/jasonzy121/Deep_Learning_Asset_Pricing), exists with no licence. It probably belongs to co-author Jason Zhu (**UNVERIFIED**).
- **Applicability to India:** Low. The model needs a large panel of characteristics plus about 178 macro series and decades of monthly data. Training a GAN on a few hundred liquid Indian names is fragile.
- **Verdict: Not justified now.**

### Jiang, Kelly & Xiu, "(Re-)Imag(in)ing Price Trends", and Murray, Xia & Xiao, "Charting by Machines"

These are two **different** papers.

- **Citations:**
    - Jiang, Kelly & Xiu, *Journal of Finance* 78(6): 3193–3249, 2023. [doi:10.1111/jofi.13268](https://doi.org/10.1111/jofi.13268).
    - Murray, Xia & Xiao, "Charting by Machines", *Journal of Financial Economics* 153: 103791, 2024. [doi:10.1016/j.jfineco.2024.103791](https://doi.org/10.1016/j.jfineco.2024.103791).
- **Does it exist?** Yes, both.
- **Claims:**
    - **Jiang, Kelly & Xiu** turn stock price charts (OHLC bars plus volume) into images and use CNNs to find the price patterns that best predict returns. The patterns they find differ from standard trend signals, predict better, and give more profitable strategies. Patterns learned from US stocks also work in international markets.
    - **Murray, Xia & Xiao** forecast returns from historical price performance with ML. The forecasts predict the cross-section of future returns, including among the 500 largest stocks, and capture effects separate from momentum and reversal. The authors argue this supports technical analysis.
- **Code:** I found no official repository for either paper. A third-party implementation exists at [lich99/Stock_CNN](https://github.com/lich99/Stock_CNN), with no licence and not confirmed as official.
- **Applicability to India:** High in principle. Both papers use **only** price and volume history, which Nivesh has from 1994 onward. The reported transfer to international markets suggests a pattern learned on US data could be tested zero-shot on Indian data. Two risks: Indian small caps have high trading costs and circuit limits (price bands) that cut off returns, and the CNN needs a lot of compute.
- **Verdict: Candidate.** Test it after the baseline exists. Use a liquid universe, such as stocks that were Nifty 200 members at the time, and judge it after costs (see `india_charges.json`).

---

## 2. Deep stock-forecasting architectures (daily panel)

### MASTER: Market-Guided Stock Transformer (Li et al., AAAI 2024)

- **Citation:** T. Li, Z. Liu, Y. Shen, X. Wang, H. Chen, S. Huang, "MASTER: Market-Guided Stock Transformer for Stock Price Forecasting", *Proc. AAAI* 38(1): 162–170, 2024. [AAAI OJS](https://ojs.aaai.org/index.php/AAAI/article/view/27767). [arXiv:2312.15235](https://arxiv.org/abs/2312.15235).
- **Does it exist?** Yes.
- **Claims:** A transformer that alternates attention within each stock (over time) and across stocks, to model short-lived correlations between stocks that also play out over time. Market-level information gates which features the model uses. The authors report that it beats earlier stock-forecasting models.
- **Code:** [SJTU-DMTai/MASTER](https://github.com/SJTU-DMTai/MASTER), MIT licence, built on Qlib.
    - The experiments use the Chinese **CSI300 and CSI800** universes.
    - The README notes that the original proprietary data source has expired, and that validation and test data covered only about 95% of stocks.
    - A 2025 notice says the validation data was built with the wrong Qlib processor.
    - Reproducing on open data needs retuning.
- **Applicability to India:** The best fit in this group. The setup is a daily panel from an emerging market with index-level market features, like Nifty 50/200/500 for India. The reproducibility notes above mean the reported numbers should not be taken at face value.
- **Verdict: Candidate.** Try it after the Gu–Kelly–Xiu-style baseline. Port it with Nivesh's own feature set and an honest walk-forward evaluation.

### StockMixer (Fan & Shen, AAAI 2024)

- **Citation:** J. Fan, Y. Shen, "StockMixer: A Simple Yet Strong MLP-Based Architecture for Stock Price Forecasting", *Proc. AAAI* 38(8): 8389–8397, 2024. [doi:10.1609/aaai.v38i8.28681](https://doi.org/10.1609/aaai.v38i8.28681).
- **Does it exist?** Yes.
- **Claims:** An all-MLP model that mixes along three axes: across indicators, across time (multi-scale patches), and across stocks (two-way stock ↔ market influence). The authors report that it beats more complex RNN, GNN and transformer models while using less memory and time.
- **Code:** [SJTU-DMTai/StockMixer](https://github.com/SJTU-DMTai/StockMixer) (redirects from SJTU-Quant), no licence file. The data covers NASDAQ, NYSE and S&P 500 and is reused from earlier stock-ranking papers.
- **Applicability to India:** Moderate. It needs only daily OHLCV and is cheap to train. The benchmarks it reports against are older ranking datasets, and their evaluation protocol has been criticised; I did not verify that criticism.
- **Verdict: Candidate (low priority).** A cheap ablation next to MASTER.

### Autoformer (Wu, Xu, Wang & Long, NeurIPS 2021)

- **Citation:** H. Wu, J. Xu, J. Wang, M. Long, "Autoformer: Decomposition Transformers with Auto-Correlation for Long-Term Series Forecasting", *NeurIPS 34*, 2021. [arXiv:2106.13008](https://arxiv.org/abs/2106.13008). Proceedings page range not verified.
- **Does it exist?** Yes.
- **Claims:** Series decomposition built into the architecture, plus an autocorrelation mechanism that replaces self-attention. The authors report about 38% relative improvement on six long-horizon benchmarks: energy, traffic, economics, weather and disease.
- **Code:** [thuml/Autoformer](https://github.com/thuml/Autoformer), MIT licence.
- **Applicability to India:** Poor for returns. The model's gains rely on trend and seasonal structure, which daily stock returns do not have. Later work found that simple linear models match or beat transformer forecasters on these benchmarks: Zeng et al., "Are Transformers Effective for Time Series Forecasting?", [arXiv:2205.13504](https://arxiv.org/abs/2205.13504). That paper's metadata was not separately verified in this review.
- **Verdict: Not justified now.**

---

## 3. Limit-order-book and microstructure models

None of these apply to Nivesh at present. They need tick-level order-book data, which NSE sells through NSE Data & Analytics under licence. Nivesh simulates at daily frequency.

| Paper | Citation | Claim (short) | Code | Verdict |
|---|---|---|---|---|
| **Deep Order Flow Imbalance** (Kolm, Turiel & Westray) | *Mathematical Finance* 33(4): 1044–1081, 2023. [doi:10.1111/mafi.12413](https://doi.org/10.1111/mafi.12413) | Deep networks fed with order-flow imbalance predict short-horizon returns better than networks fed raw order-book levels, across many Nasdaq stocks and several horizons. | No official code found | Not justified now |
| **TLOB** (Berti & Kasneci) | arXiv preprint, 2025. [arXiv:2502.15757](https://arxiv.org/abs/2502.15757) (v3, May 2025; not peer-reviewed as far as I found) | A dual-attention (spatial and temporal) transformer for order-book trend classification, tested on FI-2010, a NASDAQ dataset and Bitcoin. A simple MLP adapted to order-book data already beats earlier state-of-the-art. Predictability **fell over time (−6.68 F1)**, and defining trends net of the spread cuts performance. | [LeonardoBerti00/TLOB](https://github.com/LeonardoBerti00/TLOB), MIT | Not justified now |
| **Universal features of price formation** (Sirignano & Cont) | *Quantitative Finance* 19(9): 1449–1459, 2019. [doi:10.1080/14697688.2019.1622295](https://doi.org/10.1080/14697688.2019.1622295). [arXiv:1803.06917](https://arxiv.org/abs/1803.06917) | An LSTM trained on order-book data pooled across many US stocks predicts the direction of the next price move better than per-stock models, including on stocks it never saw. The authors read this as evidence of a universal, stationary price-formation mechanism. | No official code found | Not justified now |

The TLOB finding is the most useful one for Nivesh. Order-book predictability that disappears once the spread is accounted for supports Nivesh's policy of judging every signal **after costs**.

---

## 4. Time-series foundation models (TSFMs)

| Model | Citation | Code |
|---|---|---|
| **Chronos** (Ansari et al.) | "Chronos: Learning the Language of Time Series", *TMLR*, Oct 2024. [arXiv:2403.07815](https://arxiv.org/abs/2403.07815) | [amazon-science/chronos-forecasting](https://github.com/amazon-science/chronos-forecasting), Apache-2.0 |
| **TimesFM** (Das, Kong, Sen & Zhou) | "A decoder-only foundation model for time-series forecasting", *ICML 2024*, PMLR 235: 10148–10167. [Proceedings](https://proceedings.mlr.press/v235/das24c.html) | [google-research/timesfm](https://github.com/google-research/timesfm), Apache-2.0 |
| **Moirai** (Woo, Liu, Kumar, Xiong, Savarese & Sahoo) | "Unified Training of Universal Time Series Forecasting Transformers", *ICML 2024*, PMLR 235: 53140–53164. [Proceedings](https://proceedings.mlr.press/v235/woo24a.html) | [SalesforceAIResearch/uni2ts](https://github.com/SalesforceAIResearch/uni2ts), Apache-2.0 |

- **Claims:**
    - **Chronos** scales and quantises values into tokens and trains T5-family language models (20M–710M parameters) on them with cross-entropy loss.
    - **TimesFM** is a patched, decoder-only model pretrained on real and synthetic series. Its zero-shot accuracy comes close to supervised models trained on each dataset.
    - **Moirai** is a masked-encoder universal forecaster trained on the LOTSA corpus. It is competitive zero-shot.
- **Main caveat:** none of these models were designed or benchmarked for **stock returns**. Their reported gains are on series with structure: energy, traffic, retail and weather.

### Recent evidence on stock returns (2025–2026)

| Study | Findings |
|---|---|
| **Rahimikia, Ni & Wang, "Re(Visiting) Time Series Foundation Models in Finance"** (Nov 2025, [arXiv:2511.18578](https://arxiv.org/abs/2511.18578)) | Daily excess returns, 94 countries, 34 years. Off-the-shelf pretrained TSFMs "perform poorly in zero-shot and fine-tuning settings" against strong linear, tree-ensemble and neural baselines. Models **pretrained from scratch on financial data** do better, and the authors release such models as "FinText" on Hugging Face. **India is likely in the 94-country panel; not checked.** |
| **Noguer i Alonso & Pereira Franklin, "Pretrained Time-Series Foundation Models for Financial Return Forecasting"** (Jun 2026, [arXiv:2606.27100](https://arxiv.org/abs/2606.27100)) | TimeGPT, TimesFM-2.5, Moirai-2.0, Chronos and Chronos-2 against N-BEATS, PatchTST, iTransformer and others, on 5 US large caps with a rolling origin. The pretrained models win 8 of 10 task rankings, but gains over the **random walk are "small and sparse"**. Only 2 cases (Chronos on AMZN, Moirai-2.0 on GOOG) pass a one-sided Diebold–Mariano test. Their conclusion: TSFMs are "not universal engines" for alpha. |
| **Goel, Pasricha, Magris & Kanniainen, "Foundation Time-Series AI Model for Realized Volatility Forecasting"** (May 2025, [arXiv:2505.11163](https://arxiv.org/abs/2505.11163)) | On **volatility**, not returns, zero-shot TimesFM is a reasonable baseline. Incremental fine-tuning is needed to beat econometric models (DM and GW tests). A 2026 paper ([arXiv:2607.05291](https://arxiv.org/abs/2607.05291)) summarises it as zero-shot not beating HAR consistently; that summary was not checked against the original. |
| **Kronos (Shi et al.), "Kronos: A Foundation Model for the Language of Financial Markets"** ([arXiv:2508.02739](https://arxiv.org/abs/2508.02739); AAAI 2026 per [AAAI OJS](https://ojs.aaai.org/index.php/AAAI/article/view/39730)) | Pretrained on more than 12 billion candlestick (K-line) records from 45 exchanges. Reports a 93% RankIC improvement over the best general TSFM on price forecasting. **These are the authors' own benchmark results** and have not been independently replicated. Code: [shiyu-coder/Kronos](https://github.com/shiyu-coder/Kronos), MIT. |

**Overall reading:** on daily returns, general-purpose TSFMs used zero-shot do **not** reliably beat a random walk or a well-tuned tree ensemble. Volatility is easier to forecast than returns, and fine-tuning or finance-specific pretraining is what helps.

**Verdict for Chronos, TimesFM and Moirai: Candidate, as a benchmark only.** Add one zero-shot TSFM (Chronos-Bolt or TimesFM, both Apache-2.0) to the leaderboard as a comparison point. Do not build product features on them. Volatility forecasting is a more promising use than return forecasting. Kronos and FinText are the finance-specific options to try first if this area is revisited.

---

## 5. Backtest-overfitting and multiple-testing controls

**All five are Baseline (required).** Nivesh will compare many models, features and parameter settings on one Indian history. Without these corrections, the best-looking backtest is mostly a measure of how many things were tried.

| Method | Citation | What it does | Implementation |
|---|---|---|---|
| **Deflated Sharpe Ratio** | Bailey & López de Prado, "The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality", *J. Portfolio Management* 40(5): 94–107, 2014. [doi:10.3905/jpm.2014.40.5.094](https://doi.org/10.3905/jpm.2014.40.5.094) | Gives the probability that the true Sharpe ratio is above zero. It adjusts for the number of trials, the variance of Sharpe ratios across trials, skewness, kurtosis and sample length. | A closed-form formula of a few lines; implement directly. **Log the number of trials for every experiment.** |
| **Probability of Backtest Overfitting (PBO)** | Bailey, Borwein, López de Prado & Zhu, *J. Computational Finance* 20(4), 2017. [doi:10.21314/JCF.2016.322](https://doi.org/10.21314/JCF.2016.322). Crossref gives the online date as 2016-09. | Uses combinatorially symmetric cross-validation to estimate how often the configuration that was best in-sample ranks below the median out-of-sample. | R package `pbo` on CRAN; the algorithm is short enough to port |
| **Higher t-stat bar** | Harvey, Liu & Zhu, "… and the Cross-Section of Expected Returns", *RFS* 29(1): 5–68, 2016. [doi:10.1093/rfs/hhv059](https://doi.org/10.1093/rfs/hhv059) | Corrects for multiple testing across hundreds of published factors. A new factor should need **t > 3.0**, not 2.0. | Use it as a rule: no Nivesh signal is reported as significant below t = 3 |
| **White's Reality Check** | White, "A Reality Check for Data Snooping", *Econometrica* 68(5): 1097–1126, 2000. [doi:10.1111/1468-0262.00152](https://doi.org/10.1111/1468-0262.00152) | A bootstrap test of whether the best model from a specification search beats a benchmark. | `arch.bootstrap.SPA`, also available as `RealityCheck` in the [`arch` docs](https://arch.readthedocs.io/en/latest/multiple-comparison/multiple-comparison_examples.html) |
| **Hansen SPA** | Hansen, "A Test for Superior Predictive Ability", *J. Business & Economic Statistics* 23(4): 365–380, 2005. [doi:10.1198/073500105000000063](https://doi.org/10.1198/073500105000000063) | A studentised, re-centred version of the Reality Check with more power, less affected by poor or irrelevant models. | `arch.bootstrap.SPA`; use the consistent p-value |
| **Romano–Wolf stepdown** | Romano & Wolf, "Stepwise Multiple Testing as Formalized Data Snooping", *Econometrica* 73(4): 1237–1282, 2005. [doi:10.1111/j.1468-0262.2005.00615.x](https://doi.org/10.1111/j.1468-0262.2005.00615.x) | A stepwise bootstrap that identifies *which* strategies beat the benchmark while controlling the familywise error rate and allowing for correlation between tests. | `arch.bootstrap.StepM` |

**Applicability:** all apply directly to Indian daily data. They only need the out-of-sample return or loss series of each strategy tested. Indian daily returns are heavy-tailed and correlated, so use a block bootstrap (as `arch` does), not an i.i.d. bootstrap.

---

## 6. What is unverified in this review

!!! warning "UNVERIFIED"
    - Whether jasonzy121/Deep_Learning_Asset_Pricing is the authors' official code, and what the INFORMS replication package contains.
    - Whether official code exists for Gu–Kelly–Xiu, Jiang–Kelly–Xiu or Murray–Xia–Xiao. None was found; lich99/Stock_CNN is third-party.
    - The Autoformer NeurIPS proceedings page range.
    - The datasets used in the StockMixer *paper*. Only the repository's data was confirmed.
    - The claim that the StockMixer benchmark protocol has been criticised.
    - Whether India is in the Rahimikia et al. 94-country panel.
    - Goel et al.'s HAR comparison details.
    - The metadata of Zeng et al. (arXiv:2205.13504).
    - Kronos results (the authors' own reports only).
