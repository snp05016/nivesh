# Mathematical Framework and Architecture for a Macroeconomic Portfolio Stress-Testing Engine in Indian Equity Markets

## 1. Survey of Existing Institutional Methodologies

The architectural foundation of a world-class portfolio stress-testing engine requires a rigorous understanding of traditional asset pricing and modern risk methodologies. Institutional frameworks historically balance computational tractability with the capacity to accurately reflect market dynamics under distress. However, traditional models often rely on assumptions of normality and stationarity that collapse during severe macroeconomic shocks.

### Traditional Risk Models

The evolution of asset pricing models has produced several frameworks for estimating expected returns and decomposing systemic risk. The Capital Asset Pricing Model (CAPM) represents the earliest structural attempt to quantify risk, assuming that the expected return of an asset is a linear function of its sensitivity to the broad market portfolio [1]. The mathematical representation is expressed as:

$$E[R_i] = R_f + \beta_i(E[R_m] - R_f)$$

While CAPM provides a parsimonious, single-factor view of systemic risk through the $\beta_i$ coefficient, the framework exhibits severe weaknesses when applied to stress testing. It assumes multivariate normality of returns, homogeneous investor expectations, and the ability to borrow and lend at a risk-free rate [3]. Empirically, CAPM fails to account for well-documented market anomalies. In the context of Indian equity markets, single-factor models frequently under-represent systemic risk during liquidity-driven sell-offs, particularly in the mid-cap and small-cap segments where idiosyncratic factors dominate during crises.

To address these shortcomings, multi-factor models such as the Fama-French Three-Factor and Carhart Four-Factor models were developed to incorporate size (SMB), value (HML), and momentum (UMD) premia [2]. The Carhart equation is formulated as:

$$E[R_i] = R_f + \beta_m(E[R_m] - R_f) + \beta_s \cdot SMB + \beta_v \cdot HML + \beta_u \cdot UMD$$

These models offer superior explanatory power for long-term equity returns. However, academic factor models are inherently backward-looking and lack direct macroeconomic transmission mechanisms. A shock to the Reserve Bank of India (RBI) repo rate or a spike in Brent crude prices cannot be directly propagated through a Fama-French framework without extensive secondary modeling to map macro variables to fundamental factors.

Consequently, the industry standard relies on commercial structural risk models developed by entities such as Barra, Axioma, Bloomberg PORT, and MSCI RiskMetrics. The Barra framework, for instance, expresses asset returns through a cross-sectional multi-factor model [2]:

$$R_t = B_t f_t + \epsilon_t$$

Here, $B_t$ is an $N \times K$ matrix of exposures to $K$ factors (encompassing both fundamental and macroeconomic drivers), $f_t$ represents the $K \times 1$ vector of factor returns, and $\epsilon_t$ is the idiosyncratic risk. The portfolio variance $\sigma_p^2$ is subsequently modeled as:

$$\sigma_p^2 = w^T(B\Sigma_f B^T + \Delta)w$$

where $\Sigma_f$ is the factor covariance matrix and $\Delta$ is the diagonal idiosyncratic variance matrix [5].

These models excel at decomposing risk into systemic and idiosyncratic buckets, enabling precise attribution. The weakness of standard linear factor models, however, is their reliance on a constant covariance matrix ($\Sigma_f$) and normally distributed returns. These assumptions catastrophically fail during market crashes, which are characterized by extreme correlation breakdowns, volatility clustering, and fat-tailed distributions [6].

### Portfolio Risk and Stress Testing Models

Institutional risk estimation extends beyond variance to quantify specific tail risks. Value at Risk (VaR) represents the maximum expected loss over a specific horizon at a given confidence level $c$, defined mathematically as:

$$P(L > \text{VaR}_c) = 1 - c$$

Different methodologies approach this calculation with varying degrees of complexity and accuracy.

**Historical Simulation VaR** relies on actual historical returns to compute the empirical loss distribution. While simple to implement and free from parametric distributional assumptions, it assumes that the future will strictly resemble the past. It cannot simulate unprecedented hypothetical shocks or compound scenarios (e.g., a simultaneous 2020 COVID-like crash and a 2022 inflation spike) [8].

**Parametric VaR** assumes normally distributed returns, calculating risk as:

$$\text{VaR} = z_c \sigma_p$$

While computationally highly efficient, Parametric VaR severely underestimates tail risk due to the pronounced negative skewness and excess kurtosis of Indian equity returns.

**Monte Carlo VaR** utilizes stochastic processes, such as Geometric Brownian Motion with jump diffusion:

$$dS = \mu S \, dt + \sigma S \, dW + J \, dq$$

to simulate thousands of portfolio paths. This is highly flexible for non-linear instruments like options but computationally expensive for large portfolios.

Because VaR is not a coherent risk measure (it lacks sub-additivity), institutions increasingly rely on Expected Shortfall (ES), also known as Conditional VaR (CVaR). CVaR addresses VaR's inability to quantify the magnitude of losses extending beyond the probability threshold by calculating the probability-weighted average of all losses exceeding the VaR limit:

$$\text{CVaR}_c = E[L \mid L > \text{VaR}_c] = \frac{1}{1-c}\int_c^1 \text{VaR}_\gamma \, d\gamma$$

For institutional stress testing, CVaR is strictly superior, particularly when analyzing Indian small-cap portfolios susceptible to liquidity gaps.

**Reverse Stress Testing** inverts the traditional paradigm. Instead of shocking the market to observe the portfolio loss, it identifies the precise market scenarios that would cause a predetermined catastrophic portfolio loss limit. Mathematically, it is formulated as a constrained optimization problem to find the most probable scenario vector $x$ such that the loss function satisfies $L(x) \geq L_{\text{critical}}$, subject to historical plausibility constraints:

$$\min P(x) \quad \text{s.t.} \quad L(x) \geq L_{\text{critical}}$$

| Risk Methodology | Mathematical Core | Implementation Complexity | Applicability to Indian Equities |
|---|---|---|---|
| Historical VaR | Empirical Quantile Matching | Low | Moderate (blind to unprecedented events) |
| Parametric VaR | $z_c\sqrt{w^T\Sigma w}$ | Low | Poor (assumes normal distribution) |
| Monte Carlo VaR | Stochastic Differential Equations | High | High (excellent for non-linear instruments) |
| Expected Shortfall | $E[L \mid L > \text{VaR}_c]$ | Moderate | Excellent (captures tail risk severity) |
| Reverse Stress Test | $\min P(x) \text{ s.t. } L(x) \geq L_{\text{critical}}$ | Very High | Excellent (identifies hidden vulnerabilities) |

## 2. Institutional Macroeconomic Shock Modeling

Top-tier institutional funds, including BlackRock, Vanguard, MSCI, and AQR, utilize sophisticated predictive stress testing models to propagate macroeconomic shocks through a portfolio. The central challenge in macro stress testing is accurately modeling how an isolated shock to a macroeconomic variable ripples through interconnected global financial systems to affect specific equity holdings.

The predictive stress testing framework championed by MSCI and RiskMetrics utilizes current estimates of volatility and correlation to estimate the conditional expectation of peripheral asset movements given a shock to a core macroeconomic factor [9]. If the universe of risk factors is partitioned into a set of "shocked" core factors ($f_1$) and a set of "unshocked" peripheral factors ($f_2$), the joint distribution can be modeled as multivariate normal. The conditional expectation of the unshocked factors, given an explicit user-defined shock $\Delta f_1$, is derived through the covariance structure:

$$E[f_2 \mid f_1 = \Delta f_1] = \mu_2 + \Sigma_{21}\Sigma_{11}^{-1}(\Delta f_1 - \mu_1)$$

where $\Sigma$ represents the covariance matrix, $\Sigma_{11}$ is the covariance of the core factors, and $\Sigma_{21}$ is the cross-covariance between peripheral and core factors [10]. This mathematical propagation allows a single macroeconomic shock—such as a 20% drop in Brent Crude—to organically cascade into shifts in the USD/INR exchange rate, RBI repo rates, and subsequently into specific Indian sectors based on their historical conditional dependencies.

Firms like BlackRock model shocks through the Aladdin platform by decomposing portfolio risk across thousands of multi-asset risk factors [12]. Aladdin normalizes these exposures into Z-scores, indicating the portfolio's exposure relative to a global or regional baseline [14]. A fundamental Z-score is expressed as:

$$Z_{\text{factor}} = \frac{\beta_{\text{portfolio, factor}} - \mu_{\text{universe, factor}}}{\sigma_{\text{universe, factor}}}$$

Aladdin's architecture excels at combining fundamental equity factors (such as Value, Growth, and Size) with macroeconomic factors (Interest Rates, Credit Spreads, and Foreign Exchange) into a unified covariance matrix. This enables multi-variable hypothetical scenario testing where complex market interactions are maintained [8].

Other institutional players employ variations of these principles. Bridgewater Associates evaluates shock propagation through an All-Weather risk-parity lens, mapping macro shocks directly to growth and inflation expectations, and rebalancing the portfolio based on asset class volatility contributions. Quantitative funds like AQR utilize momentum and value-based stress testing, analyzing how factor crowding exacerbates sell-offs during liquidity crunches. JPMorgan and Goldman Sachs employ extensive Monte Carlo engines combined with copula functions to model the joint tail dependence of assets, ensuring that extreme macro shocks accurately simulate the non-linear clustering of defaults and equity drawdowns during banking crises or geopolitical events.

## 3. Factor-Based Stress Testing Engine Design

To construct a stress-testing engine uniquely tailored for Indian equities, the underlying risk factors must be carefully chosen, mathematically represented, and normalized to ensure cross-compatibility in the covariance matrix. The platform must support specific Indian market nuances, including the outsized impact of Foreign Institutional Investor (FII) flows and the structural bifurcation between large-cap and small-cap liquidity.

### Market and Macro Factor Definitions

The engine requires a robust set of fundamental and macroeconomic variables. Below is the framework for modeling these inputs:

| Factor Classification | Factor Proxy | Mathematical Representation | Distribution / Scaling Methodology |
|---|---|---|---|
| Broad Market | Nifty 50 Index | Log return: $\ln(P_t/P_{t-1})$ | Fat-tailed (Student's t); requires daily variance scaling. |
| Market Proxy | Sensex | Log return: $\ln(P_t/P_{t-1})$ | Highly correlated to Nifty; serves as a cross-validation node. |
| Size / Risk | Nifty Midcap / Smallcap | Log return: $\ln(P_t/P_{t-1})$ | High market beta; extreme left-tail skewness during sell-offs. |
| Economic Growth | GDP Growth Rate | Absolute shift ($\Delta\%$) | Low-frequency data interpolated via MIDAS regressions. |
| Inflation | CPI YoY | Absolute shift ($\Delta\%$) | Mean-reverting; dictates discount rate adjustments. |
| Interest Rates | RBI Repo / 10Y G-Sec | Absolute yield shift ($\Delta \text{bps}$) | Modeled via yield curve parallel, steepening, and flattening shifts. |
| Currency | USD/INR Spot | Percentage change | Positively skewed due to historical INR depreciation trends. |
| Commodities | Brent Crude / Gold | Percentage change | High kurtosis; Brent shocks heavily impact Indian current accounts. |
| Volatility | India VIX | Percentage change | Log-normal distribution; strongly mean-reverting. |
| Liquidity Flows | FII & DII Net Flows (₹ Cr) | Rolling Z-score normalizations | Non-stationary absolute values mandate moving-window standardization. |

### Scaling and Normalization

Integrating disparate macroeconomic variables—measured in percentages, basis points, or nominal currency values—with equity returns requires rigorous normalization. FII and DII flows, which are expressed in absolute Crores (₹ Cr) and exhibit extreme non-stationarity over long horizons, must be converted into standardized innovations. The engine utilizes a rolling Z-score over a 252-day trading window to measure standard deviation shocks to liquidity flows:

$$z_{\text{FII},t} = \frac{\text{Flow}_t - \mu_{252}}{\sigma_{252}}$$

This scaling ensures that a sudden withdrawal of ₹50,000 Cr is appropriately recognized as an extreme standard deviation event relative to the prevailing market regime, rather than an absolute scalar value.

### Shock Magnitude Estimation

The engine maps user-defined hypothetical shocks to historical standard deviations to assess plausibility. For instance, a user-defined "Nifty -20%" scenario represents an extreme multi-sigma event. The mathematical framework calibrates these shocks utilizing Extreme Value Theory (EVT), specifically the Generalized Pareto Distribution (GPD) for exceedances over a threshold, allowing the engine to map hypothetical inputs to appropriate probability density quantiles. This ensures that the peripheral variables react non-linearly to extreme shocks compared to minor market fluctuations.

## 4. Estimation of Stock Sensitivities

A core requirement of the mathematical engine is the precise estimation of the sensitivity ($\beta$) of individual Indian stocks to the defined macroeconomic and market factors. Traditional methods rely on rolling Ordinary Least Squares (OLS) regressions.

### Rolling Regressions and Limitations

The standard rolling regression model estimates sensitivities over a fixed window (e.g., 252 days):

$$R_{i,t} = \alpha_i + \beta_{i,\text{market}} R_{\text{Nifty},t} + \beta_{i,\text{oil}} \Delta\text{Oil}_t + \epsilon_{i,t}$$

While straightforward, rolling regressions suffer from a "ghosting" effect, where an extreme outlier event heavily influences the beta for exactly 252 days before abruptly dropping out of the sample, creating an artificial step-change in risk exposure [16]. Furthermore, in Indian small-cap equities, illiquidity and asynchronous trading cause severe measurement errors in OLS estimations.

### Bayesian Shrinkage Estimators (Vasicek Model)

To correct for the estimation error inherent in illiquid stocks, the framework implements a Bayesian shrinkage estimator based on Vasicek's (1973) methodology [17]. The Vasicek model shrinks the time-series estimate of a stock's beta ($\hat\beta_{TS}$) toward the cross-sectional mean of its peer group, sector, or the broader market ($\beta_{\text{prior}}$). The shrinkage equation is formulated as:

$$\beta_{\text{shrink},i} = w_i \hat\beta_{TS,i} + (1-w_i)\beta_{\text{prior}}$$

The shrinkage weight $w_i$ is determined by the relative precisions (inverse variances) of the estimates:

$$w_i = \frac{\sigma_{\text{prior}}^2}{\sigma_{\text{prior}}^2 + \sigma_{\hat\beta_{TS,i}}^2}$$

If a small-cap stock has a highly volatile and statistically insignificant beta due to sparse trading data, its standard error $\sigma_{\hat\beta_{TS,i}}^2$ will be large. Consequently, $w_i$ tends toward 0, and the assigned beta gracefully defaults to the sector average [16]. This mathematical adjustment is critical to prevent spurious leverage assumptions in the stress engine that would otherwise wildly overestimate or underestimate specific stock impacts during a crash.

### Time-Varying Sensitivities via Kalman Filtering

To model dynamic, time-varying betas ($\beta_t$) that adapt in real-time to structural regime shifts, the framework utilizes a state-space representation estimated via the Kalman Filter [1]. The system is defined by two equations.

The **Observation Equation** models the observed returns:

$$R_{i,t} = \alpha_t + \beta_{i,t}^T F_t + \epsilon_{i,t}, \quad \epsilon_{i,t} \sim N(0, H_t)$$

The **State Equation** models the unobserved, evolving true sensitivities as a random walk:

$$\beta_{i,t} = \beta_{i,t-1} + \eta_{i,t}, \quad \eta_{i,t} \sim N(0, Q_t)$$

The Kalman Filter operates in two steps. The **Prediction Step** projects the current state and error covariance forward:

$$\hat\beta_{i,t \mid t-1} = \hat\beta_{i,t-1\mid t-1}$$

$$P_{t\mid t-1} = P_{t-1\mid t-1} + Q_t$$

The **Update Step** incorporates the new return observation $R_{i,t}$, weighted by the Kalman Gain $K_t$:

$$K_t = P_{t\mid t-1}F_t\left(F_t^T P_{t\mid t-1}F_t + H_t\right)^{-1}$$

$$\hat\beta_{i,t\mid t} = \hat\beta_{i,t\mid t-1} + K_t\left(R_{i,t} - F_t^T\hat\beta_{i,t\mid t-1}\right)$$

This recursive updating provides a highly responsive sensitivity measure that accurately reflects rapidly changing corporate risk profiles—such as a heavily leveraged Indian infrastructure company suddenly exhibiting massive sensitivity to RBI rate hikes—without the lagging artifacts of rolling windows.

## 5. The Mathematical Engine Design

The core of the stress-testing platform evaluates the equation:

$$\text{Portfolio Loss} = f(\text{Market Shock}, \text{Factor Shock}, \text{Sector Shock}, \text{Liquidity Shock}, \text{Correlation Shock})$$

### Impact Equations

For a given asset $i$, the **Stock Impact Equation** calculates the expected return under stress by summing its Kalman-filtered sensitivities to the vector of shocked factors $\Delta F$:

$$E[R_i \mid \Delta F] = \alpha_i + \sum_{k=1}^{K} \beta_{i,k}^{\text{Kalman}} \cdot \Delta F_k$$

The **Sector Impact Equation** aggregates these values based on the market capitalization weights $W_i$ of the constituents within the sector index $S$:

$$E[R_S \mid \Delta F] = \sum_{i \in S} W_i \left(E[R_i \mid \Delta F]\right)$$

The overarching **Portfolio Impact Equation** aggregates the weighted individual stock impacts across the user's holdings, while explicitly subtracting the non-linear penalty terms for correlation breakdowns ($\Psi_{\text{correlation}}$) and liquidity evaporation ($\Lambda_{\text{liquidity}}$), which are derived in later sections:

$$\text{Portfolio Loss} = \sum_{i=1}^{N} w_i \left(E[R_i \mid \Delta F]\right) - \Psi_{\text{correlation}} - \Lambda_{\text{liquidity}}$$

### Stress Loss and Tail Risk Equations

To provide a VaR-like stress loss metric, the **Tail Risk Equation** computes the conditional variance of the portfolio entirely under the crisis regime ($\Sigma_{\text{stress}}$). The **Stress Loss Equation** calculates the Expected Shortfall at the 99% confidence interval using the Cornish-Fisher expansion to adjust for the skewness ($S$) and kurtosis ($K$) of the portfolio returns during historical shocks:

$$z_{CF} = z_c + \frac{1}{6}(z_c^2 - 1)S + \frac{1}{24}(z_c^3 - 3z_c)K - \frac{1}{36}(2z_c^3 - 5z_c)S^2$$

The **Worst Case Equation** is thus defined as:

$$\text{Worst Case Stress Loss}_{99\%} = \text{Portfolio Loss} - \left(z_{CF} \times \sqrt{w^T \Sigma_{\text{stress}} w}\right)$$

The **Expected Drawdown Equation** evaluates the maximal peak-to-trough decline over the simulated stress horizon, utilizing Monte Carlo trajectory simulations incorporating the stressed drift and volatility parameters.

## 6. Scenario Generation

The engine facilitates both historical stress replay and the generation of pure hypothetical stress events.

### Historical Stress Calibration

A vital institutional practice is the "replay" of historical stress events mapping historical shocks onto *current* portfolio exposures [8].

- **2008 Global Financial Crisis:** Calibrated by a simultaneous Nifty crash exceeding 50%, extreme global liquidity contraction, and systemic banking failures.
- **2020 COVID Crash:** Modeled as a rapid, exogenous V-shaped shock characterized by India VIX spiking above 70, synchronized global correlations, and massive FII outflows.
- **2022 Inflation Shock:** Features sustained RBI repo rate hikes, continuous USD/INR depreciation, and growth stock underperformance relative to value.
- **2024 Election Volatility:** Characterized by extreme intraday Nifty volatility (exceeding 6% swings) and rapid, localized sector rotations.

The historical calibration engine isolates the crisis window $[t_0, t_1]$, extracts the maximum drawdown vector $\Delta F_{\text{historical}}$ for all factors, and feeds this empirical shock vector directly into the Stock Impact Equation.

### Hypothetical Stress and Calibration Techniques

For hypothetical stress inputs—such as a simultaneous "Nifty -20%," "Oil +50%," and "FII Outflow ₹100,000 Cr"—the framework relies on copula theory to ensure the joint probability of the input scenario is mathematically plausible. If a user inputs a fundamentally contradictory scenario (e.g., Nifty surges 30% while the VIX spikes 200%), the system applies Mahalanobis distance matching to constrain the peripheral shocks to the nearest historically plausible subspace. The Mahalanobis distance $D_M$ between the proposed shock vector $x$ and the mean of historical shocks $\mu$ is:

$$D_M(x) = \sqrt{(x-\mu)^T \Sigma^{-1}(x-\mu)}$$

If $D_M(x)$ exceeds a critical threshold defined by the $\chi^2$ distribution, the engine scales the parameters back into the region of plausibility before executing the stress test, preventing nonsensical output artifacts.

## 7. Liquidity Risk

In Indian markets, liquidity risk represents a profound source of asymmetric downside. While Nifty 50 constituents boast deep order books and continuous liquidity, mid-cap and small-cap stocks exhibit extreme bid-ask spreads and evaporating market depth during panic sell-offs.

### The NSE Impact Cost Model

The National Stock Exchange (NSE) formally defines "Impact Cost" as the percentage degradation experienced relative to an ideal price when executing a predetermined quantity of shares [23]. The mathematical definition is:

$$\text{Ideal Price} = \frac{\text{Best Buy Price} + \text{Best Sell Price}}{2}$$

$$\text{Impact Cost}\,(\%) = \left(\frac{\text{Actual Execution Price} - \text{Ideal Price}}{\text{Ideal Price}}\right) \times 100$$

This metric is a stringent measure of liquidity; the NSE requires stocks to reliably maintain an impact cost below 0.50% for a ₹2 Crore trade to be eligible for Nifty 50 index inclusion [25].

### Estimating Liquidation Losses

For a portfolio stress-testing engine, projecting the total impact cost requires modeling the slippage of liquidating a user's entire holdings. Institutional literature heavily relies on the "Square-Root Law of Market Impact" established by Almgren and Chriss [27]. The expected liquidation loss (price impact) $\Delta P_i$ for executing quantity $Q_i$ in an asset with average daily volume $V_i$ and daily volatility $\sigma_i$ is modeled as a function of temporary and permanent impact:

$$\Delta P_i = \gamma \cdot \sigma_i \sqrt{\frac{Q_i}{V_i}}$$

where $\gamma$ is an empirically calibrated universal constant (typically ranging from 0.1 to 0.3 for global equities, calibrated specifically to Indian market microstructure).

The total Liquidity Shock penalty ($\Lambda_{\text{liquidity}}$) applied to the portfolio is derived by aggregating the bid-ask crossing and the market impact:

$$\Lambda_{\text{liquidity}} = \sum_{i=1}^{N} P_i Q_i \left(\text{Base Spread}_i + \gamma \sigma_i \sqrt{\frac{Q_i}{V_i}}\right)$$

Crucially, during a modeled "Crash Scenario," the engine artificially suppresses the assumed volume $V_i$ by 50% to 80% to simulate evaporating market depth. Because the variable $V_i$ sits in the denominator under a square root, this liquidity shock exponentially inflates the modeled liquidation loss for small-cap heavy portfolios, mathematically penalizing the illusion of liquidity.

## 8. Correlation Breakdowns

Traditional risk engines utilize static correlation matrices that catastrophically fail during macro shocks because diversification physically disappears. Historically uncorrelated assets suddenly move in lockstep as investors liquidate across all asset classes indiscriminately (correlation $\to 1.0$) [6]. The engine mathematically captures this "correlation breakdown" using two primary approaches.

### The DCC-GARCH Framework

To model dynamic correlations, the engine implements a Dynamic Conditional Correlation (DCC) Generalized Autoregressive Conditional Heteroskedasticity (GARCH) model [33]. The covariance matrix $H_t$ is decomposed into conditional standard deviations and a time-varying correlation matrix $R_t$:

$$H_t = D_t R_t D_t$$

where $D_t = \text{diag}(\sqrt{h_{11,t}}, ..., \sqrt{h_{NN,t}})$ [36].

**Step 1:** The individual variances $h_{ii,t}$ are modeled using a standard univariate GARCH(1,1) process:

$$h_{ii,t} = \omega_i + \alpha_i \epsilon_{i,t-1}^2 + \beta_i h_{ii,t-1}$$

**Step 2:** The DCC innovation governs the evolution of a correlation proxy matrix $Q_t$. By utilizing the standardized residuals $\eta_t = D_t^{-1}\epsilon_t$, the matrix evolves as:

$$Q_t = (1 - a - b)\bar{Q} + a(\eta_{t-1}\eta_{t-1}^T) + bQ_{t-1}$$

where $\bar{Q}$ is the unconditional covariance matrix of the standardized residuals, and $a$ and $b$ are scalar parameters governing the speed of correlation reaction and persistence [38].

**Step 3:** The actual dynamic conditional correlation matrix is extracted via normalization:

$$R_t = \text{diag}(Q_t)^{-1/2} Q_t \, \text{diag}(Q_t)^{-1/2}$$

During a simulated stress test, the engine nullifies phantom diversification benefits by abandoning the unconditional $\bar{Q}$ and directly applying the elevated, stressed $R_{\text{crisis}}$ matrix generated during historical spikes.

### The Broken Arrow Stress Test

As a supplementary framework, the engine can employ the "Broken Arrow" predictive stress methodology pioneered by MSCI [9]. This approach models the joint distribution of asset returns as a mixture of two multivariate normal distributions: one representing "quiet" periods with low volatility and loose correlations, and another representing "hectic" periods with high volatility and severe cross-asset dependency. During stress calculations, the engine forcibly switches the probability weighting entirely to the "hectic" covariance matrix [41].

## 9. Regime Detection

Determining whether the Indian equity market is currently operating in a "Normal" or "Crisis" state is critical for calibrating the baseline starting parameters of a stress test. The framework achieves this through automated regime detection.

### Markov Regime Switching (MRS) and Hidden Markov Models (HMM)

The engine utilizes a Markov Regime Switching model to infer the latent market state [43]. Let the unobservable state variable be $S_t \in \{1, 2\}$, where State 1 denotes a "Bull/Low Volatility" regime and State 2 denotes a "Crash/High Volatility" regime. The returns of the Nifty 50 follow a state-dependent normal distribution:

$$R_t \mid S_t \sim N(\mu_{S_t}, \sigma_{S_t}^2)$$

The probability of transitioning between these regimes is governed by a transition probability matrix $P$:

$$P = \begin{bmatrix} p_{11} & p_{12} \\ p_{21} & p_{22} \end{bmatrix} = \begin{bmatrix} p_{11} & 1-p_{11} \\ 1-p_{22} & p_{22} \end{bmatrix}$$

where $p_{ij} = P(S_t = j \mid S_{t-1} = i)$ [46].

The model parameters $\Theta = (\mu_1, \mu_2, \sigma_1^2, \sigma_2^2, p_{11}, p_{22})$ are estimated iteratively using the Expectation-Maximization (EM) algorithm. Through the Hamilton filter, the engine continuously calculates the filtered probability of being in the crash regime: $P(S_t = 2 \mid R_1 \dots R_t)$. If this probability crosses a critical threshold (e.g., 0.50), the UI dynamic changes, and the stress engine automatically defaults to initiating tests from a baseline of stressed correlations and elevated liquidity penalties, reflecting the reality of the ongoing market environment.

## 10. Machine Learning Enhancements

While econometric models (like GARCH and Kalman filters) provide rigorous mathematical foundations and interpretability, non-linear machine learning architectures can enhance the calibration of complex macro-to-micro transmission mechanisms. The research evaluates several model candidates:

| Model Architecture | Applicability to Macro Stress Testing | Interpretability | Implementation Difficulty |
|---|---|---|---|
| XGBoost / LightGBM | Excellent for modeling non-linear fundamental factor impacts (e.g., predicting specific sector default clustering during rate hikes). | High (via SHAP values) | Low |
| Random Forest | Robust ensemble method for feature selection, but struggles to extrapolate extreme events outside historical training data boundaries. | Moderate | Low |
| LSTM | Valuable for identifying temporal dependencies in high-frequency order book data to estimate real-time liquidity evaporation. | Low | High |
| Temporal Fusion Transformers (TFT) | Enables multi-horizon forecasting of macro variables (USDINR, Brent). Allows conditioning on known future events (e.g., General Election dates). | Moderate (via Attention weights) | Very High |
| Graph Neural Networks (GNN) | Outstanding for modeling supply chain contagion and inter-corporate credit risks (e.g., estimating cross-defaults in Indian conglomerate structures). | Low | Very High |

**Strategic Implementation:** The framework incorporates Gradient Boosting algorithms (XGBoost) to estimate the non-linear tail-risk sensitivities mapping macro shocks to individual stock returns. Interpretability is preserved through SHAP (Shapley Additive exPlanations) values, allowing the engine to explicitly justify its loss projections to the end user by isolating the exact feature (e.g., "High debt-to-equity ratio") driving a predicted drawdown.

## 11. Portfolio Concentration Risk

A severe macroeconomic shock disproportionately impacts portfolios harboring hidden, highly correlated concentrations. A user may own thirty different Indian stocks, assuming diversification, while unknowingly carrying extreme concentration in a single factor (e.g., high beta) or sector (e.g., Financials) [32].

### The Herfindahl-Hirschman Index (HHI)

Adapted from antitrust economics, the Herfindahl-Hirschman Index (HHI) provides a robust, mathematical measure of portfolio concentration across individual stocks, sectors, or stylistic factors [48]. The HHI is calculated by squaring the percentage weight of each constituent and summing the results:

$$\text{HHI} = \sum_{i=1}^{N} (w_i \times 100)^2$$

For an equity portfolio, the HHI thresholds provide clear risk delineation:

- **HHI < 1,500:** Indicates a well-diversified portfolio structure.
- **HHI 1,500 – 2,500:** Indicates moderate concentration.
- **HHI > 2,500:** Flags high concentration, rendering the portfolio highly vulnerable to idiosyncratic sector shocks or regulatory policy changes [52].

### Marginal Risk Contribution (MRC)

To illuminate exactly *which* holding is disproportionately driving the stress loss, the engine decomposes the total portfolio volatility $\sigma_p$. Utilizing Euler's theorem for homogeneous functions of degree one, the Marginal Risk Contribution (MRC) of asset $i$ is defined as the partial derivative of the total portfolio risk with respect to its weight $w_i$ [5]. Assuming a factor structure where $\Sigma$ is the estimated asset covariance matrix, the MRC is computed as:

$$\text{MRC}_i = \frac{\partial \sigma_p}{\partial w_i} = \frac{(\Sigma w)_i}{\sigma_p}$$

The absolute Risk Contribution (RC) of the asset to the total portfolio volatility is then $w_i \times \text{MRC}_i$. During a stress test, the engine utilizes the stressed covariance matrix $\Sigma_{\text{crisis}}$ to compute the MRC. It then outputs a sorted list of the assets by their Risk Contribution, flagging the top contributors as the portfolio's "Most Vulnerable Holdings."

## 12. User-Facing Outputs

Translating complex multidimensional mathematics into actionable insights for the end-user requires a system of normalized, mathematically justified scoring metrics. The platform generates the following outputs:

- **Risk Score (0–100):** A baseline gauge derived from the portfolio's unconditional standard deviation mapped to a sigmoid function. It provides a generalized metric of everyday volatility.
- **Stress Score (0–100):** A normalized percentile rank of the portfolio's Expected Shortfall (CVaR) relative to a benchmark index (e.g., Nifty 50). A score of 100 indicates maximum resilience under distress.
- **Macro Fragility Score:** A weighted aggregation of the portfolio's Kalman-filtered betas specific to adverse macroeconomic factors (Inflation, Repo Rates, Brent Crude, USDINR depreciation).
- **Liquidity Score:** Derived strictly from the Square-Root Impact Cost model. It represents the expected percentage loss (slippage) if the user were forced to liquidate the entire portfolio within a 2-day window under stressed volume constraints.
- **Concentration Score:** An inverted, logarithmic mapping of the calculated Sector and Factor HHI values, penalizing portfolios that masquerade as diversified while holding highly correlated assets.
- **Tail Risk Score:** Calculated as the mathematical difference between the Parametric VaR (which assumes a normal distribution) and the Monte Carlo Expected Shortfall (which captures fat tails). A vast divergence highlights severe, hidden vulnerability to "Black Swan" events.

## 13. Recommended Architecture

To facilitate implementation by quantitative engineering teams, the engine's architectural complexity is staggered into three distinct tiers.

| Parameter | Tier 1 (MVP) | Tier 2 (Institutional Grade) | Tier 3 (World-Class Quant System) |
|---|---|---|---|
| Core Methodology | Historical Simulation VaR + Static Beta OLS sensitivities. | Predictive Stress Testing + Vasicek Bayesian Shrinkage Betas. | DCC-GARCH Correlation + Kalman Dynamic Betas + Regime Switching. |
| Data Requirements | End-of-day stock returns, basic sector indices (5 years). | Broad macro factors (Rates, FX, Flows), fundamentally normalized data. | High-frequency bid-ask spread data, order book depth, tick-level index data. |
| Computational Complexity | Very Low ($O(N)$ operations). | Moderate (requires matrix inversion and Cholesky decompositions). | Extremely High (requires non-linear optimization for MLE of GARCH). |
| Accuracy / Interpretability | Moderate / High. | High / High. | Very High / Moderate (complex underlying math requires translation). |
| Implementation Effort | 2–4 weeks. Suitable for retail applications but blind to regime shifts. | 3–4 months. Requires reliable macroeconomic data pipelines. | 6–9 months. Requires dedicated High-Performance Computing (HPC) cloud infrastructure. |

## 14. Final Recommendation and Implementation Blueprint

If tasked with building an industry-leading macroeconomic stress-testing feature for an Indian investing platform today, the recommendation is to implement a **Tier 2.5 Hybrid Architecture**. This strikes the optimal balance, combining the robustness of institutional predictive stress models (MSCI/BlackRock) with the advanced econometric techniques (Vasicek Shrinkage, Square-Root Liquidity) required to navigate the Indian market's unique liquidity bifurcations and structural dynamics.

### The Exact Mathematical Workflow

**Step 1: Factor Estimation & Shrinkage**

Estimate raw asset sensitivities using an exponentially weighted moving average (EWMA) OLS to prioritize recent market structures. Immediately apply the Vasicek Bayesian shrinkage to stabilize small-cap and mid-cap betas against the sector mean:

$$\hat\beta_{i,k}^{\text{Final}} = \left(\frac{\sigma_{\text{sector}}^2}{\sigma_{\text{sector}}^2 + \sigma_{\beta_{i,k}}^2}\right)\hat\beta_{i,k}^{\text{EWMA}} + \left(\frac{\sigma_{\beta_{i,k}}^2}{\sigma_{\text{sector}}^2 + \sigma_{\beta_{i,k}}^2}\right)\beta_{\text{sector}}$$

**Step 2: Predictive Covariance Stressing**

When a user selects a macro scenario (e.g., "RBI Rate Hike +100bps"), partition the system into the shocked factor ($\Delta f_1$) and unshocked factors ($f_2$). Calculate the conditional shock propagation:

$$\Delta f_2 = \mu_2 + \Sigma_{21}\Sigma_{11}^{-1}(\Delta f_1 - \mu_1)$$

Apply the Broken Arrow Stress Test heuristic [9]: abandon the standard covariance matrix $\Sigma_{\text{normal}}$ and substitute a stressed covariance matrix $\Sigma_{\text{crisis}}$ derived from historical crisis periods. This natively forces correlation convergence across asset classes without the immense real-time computational overhead required by continuous DCC-GARCH updates.

**Step 3: Portfolio Aggregation**

Compute the baseline base impact for each stock $i$:

$$R_i^{\text{stress}} = \alpha_i + \sum_{k=1}^{K} \hat\beta_{i,k}^{\text{Final}} \cdot \Delta F_k$$

Calculate the total base loss:

$$L_{\text{base}} = \sum_{i=1}^{N} w_i R_i^{\text{stress}}$$

**Step 4: Asymmetric Liquidity Penalty Integration**

Inject the NSE Impact Cost parameters into the Almgren-Chriss Square-Root model. Radically reduce the assumed Average Daily Volume ($V_i$) by 60% to simulate a crisis environment where market depth evaporates:

$$\Lambda_{\text{liquidity}} = \sum_{i=1}^{N} w_i \left(\text{Base Spread}_i + \gamma \cdot \sigma_i \sqrt{\frac{Q_i}{0.4 \cdot V_i}}\right)$$

**Step 5: Final Output Generation**

Compute the final portfolio impact:

$$\text{Total Stress Loss} = L_{\text{base}} - \Lambda_{\text{liquidity}}$$

Simultaneously, calculate the Herfindahl-Hirschman Index ($HHI$) and the Marginal Risk Contributions using the crisis covariance matrix ($\Sigma_{\text{crisis}}$) to generate the concentration and vulnerability scores for the front-end user interface.

### Engineering Roadmap & Data Pipeline

1. **Data Ingestion Layer:** Automate nightly ETL pipelines fetching the NSE Bhavcopy (for ADV and Volume inputs), FII/DII net flows from NSDL, and RBI macroscopic datasets.
2. **Factor Covariance Engine (Batch):** Execute nightly batch processing (via Python/NumPy) to compute the 252-day and 1000-day covariance matrices ($\Sigma_{\text{normal}}$ and $\Sigma_{\text{crisis}}$).
3. **Beta Computation (Batch):** Pre-calculate the Vasicek-shrunk betas for all 2,000+ tradable Indian equities against the defined fundamental and macro factors. Cache these results in a high-speed key-value store (e.g., Redis).
4. **Inference API (Real-Time):** Upon a user triggering a stress test, the backend retrieves the user's holdings $\{w_i, Q_i\}$, pulls the pre-computed betas and covariances, executes the conditional expectation matrix multiplications ($O(K^3)$ operations, highly optimized), applies the non-linear liquidity penalty, and returns the JSON payload containing the final risk scores.
5. **Validation Methodology:** Rigorously backtest the engine by initializing it with historical portfolio states from December 31, 2019. Run the "COVID Crash" scenario, and compare the engine's predicted portfolio loss against the actual realized drawdowns experienced in March 2020. Iteratively calibrate the liquidity scalar $\gamma$ and the shrinkage prior variances until the mean absolute percentage error (MAPE) is minimized across out-of-sample data sets.

This comprehensive mathematical architecture provides a scalable, computationally efficient, and uniquely India-optimized stress-testing framework primed for direct implementation by quantitative engineering teams.

---

## Works Cited

1. Learning about Beta: Time-Varying Factor Loadings, Expected Returns, and the Conditional CAPM — https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr193.pdf
2. Dynamic Stock Selection Strategies: A Structured Factor Model Framework — https://faculty.mccombs.utexas.edu/carlos.carvalho/CarvalhoLopesAguilarFinal.pdf
3. Challenges of Using Beta in Financial Models, Phoenix Strategy Group — https://www.phoenixstrategy.group/blog/challenges-of-using-beta-in-financial-models
4. Long-History Principal Component Analysis in a Dynamic Factor Model with Weak Loadings — https://pubsonline.informs.org/doi/10.1287/opre.2024.1134
5. Marginal Risk Contribution under Factor structure, Quantitative Finance Stack Exchange — https://quant.stackexchange.com/questions/71395/marginal-risk-contribution-under-factor-structure
6. Beyond Value at Risk: What the 2025 Tariff Shock Revealed, TS Imagine — https://tsimagine.com/insights/beyond-value-at-risk-2025-tariff-shock-risk-managers/
7. Evaluating "correlation breakdowns" during periods of market volatility, BIS — https://www.bis.org/publ/confer08k.pdf
8. Power of Stress Testing with Aladdin Wealth, BlackRock — https://www.blackrock.com/aladdin/products/aladdin-wealth/insights/power-of-stress-testing
9. A Stress Test to Incorporate Correlation Breakdown, MSCI — https://www.msci.com/www/research-report/a-stress-test-to-incorporate/0184499114
10. Return to RiskMetrics: The Evolution of a Standard, MSCI — https://www.msci.com/documents/10199/dbb975aa-5dc2-4441-aa2d-ae34ab5f0945
11. Stress Testing Portfolios: Best Practices for Shockwave Propagation, MSCI — https://www.msci.com/research-and-insights/paper/stress-testing-portfolios-best-practices-for-shockwave-propagation
12. Risk Management Software | Aladdin Risk, BlackRock — https://www.blackrock.com/aladdin/products/aladdin-risk
13. Understand asset risk by decomposing into factors, BlackRock — https://www.blackrock.com/aladdin/products/aladdin-wealth/insights/risk-layers
14. Equity Factor Exposures Methodology, BlackRock — https://www.blackrock.com/us/financial-professionals/tools/factor-box-methodology
15. How to measure risk for structured products, BlackRock — https://www.blackrock.com/aladdin/products/aladdin-wealth/insights/value-of-revaluation
16. How to estimate beta?, EconStor — https://www.econstor.eu/bitstream/10419/172871/1/dp-617.pdf
17. Adaptive Beta Shrinkage estimation of covariance matrices, Taylor & Francis — https://www.tandfonline.com/doi/full/10.1080/10293523.2025.2553255
18. Adaptive Beta Shrinkage estimation of covariance matrices, Investment Analysts Journal — https://journals.co.za/doi/10.1080/10293523.2025.2553255
19. Bayesian Shrinkage Factor, Math Stack Exchange — https://math.stackexchange.com/questions/1016920/bayesian-shrinkage-factor
20. NBER Working Paper Series: Simpler Better Market Betas — https://www.nber.org/system/files/working_papers/w26105/w26105.pdf
21. Simply Better Market Betas around the Globe, Critical Finance Review — https://cfr.ivo-welch.info/forthcoming/papers/chung2024simply.pdf
22. Particle Filtering Estimation of Regime Switching Factor Model and Its Application in Statistical Arbitrage Strategy, MDPI — https://www.mdpi.com/1911-8074/18/10/549
23. The Impact of Impact Cost, Angel One — https://www.angelone.in/knowledge-center/share-market/the-impact-of-impact-cost
24. Impact Cost, NSE India — https://www.nseindia.com/static/products-services/indices-impact-cost
25. FAQs, NIFTY Indices — https://www.niftyindices.com/resources/index-concepts/faqs
26. Stock Market Indices: Types, Calculation & Importance in Trading & Investment, CapMint — https://www.capmint.com/learn/articles/stock-market-indices
27. Optimal solution of the liquidation problem under execution and price impact risks, UNICAM — https://pubblicazioni.unicam.it/retrieve/69ab6e55-129f-4ce0-b9d5-5d91fae9824a/liquidation_rev_def.pdf
28. Three models of market impact, Baruch MFE Program — https://mfe.baruch.cuny.edu/wp-content/uploads/2012/09/Chicago2016OptimalExecution.pdf
29. Portfolio liquidity-Adjusted Value-At-Risk — https://scielo.org.za/pdf/sajems/v11n2/06.pdf
30. Optimal Execution of Portfolio Transactions — https://www.smallake.kr/wp-content/uploads/2016/03/optliq.pdf
31. Modern Portfolio Theory, RupeeCase Learn — https://www.rupeecase.com/learn/path-4/module-4-1-modern-portfolio-theory.html
32. Portfolio Correlation Analysis for Stocks, Crypto & ETFs: Risk Management Guide — https://www.guardfolio.ai/blog/correlation
33. Shifting Correlations: How Trade Policy Uncertainty Alters Stock-T Bill Relationships, arXiv — https://arxiv.org/html/2603.25285v1
34. An empirical study of the dynamic correlation of Japanese stock returns — https://www.boj.or.jp/en/research/wps_rev/wps_2015/data/wp15e07.pdf
35. GARCH(1,1) - DCC, frds — https://frds.io/algorithms/garch-dcc/
36. Spatial Multivariate GARCH Models and Financial Spillovers, MDPI — https://www.mdpi.com/1911-8074/16/9/397
37. Correlation Analysis Documentation, V-Lab — https://vlab.stern.nyu.edu/docs/correlation
38. DCC (Dynamic Conditional Correlations), Estima — https://estima.com/webhelp/topics/mvgarch-dcc.html
39. Example Quant Finance DCC-GARCH Stocks Analysis, Kaggle — https://www.kaggle.com/code/unmoved/example-quant-finance-dcc-garch-stocksanalysis
40. mgarch dcc — Dynamic conditional correlation multivariate GARCH model, Stata — https://www.stata.com/manuals/tsmgarchdcc.pdf
41. Bridging the Last Mile: A Transmission Channel Framework for Derivatives Stress Testing Under Climate Scenarios, MDPI — https://www.mdpi.com/1911-8074/19/6/417
42. Market-Driven Scenarios, BlackRock — https://www.scribd.com/document/876554341/Market-driven-scenarios-BlackRock
43. A Markov Regime Switching Approach to Characterizing Financial Time Series, Medium — https://medium.com/@cemalozturk/a-markov-regime-switching-approach-to-characterizing-financial-time-series-a5226298f8e1
44. Multi-regime Markov-switching models with time-varying transition probabilities, arXiv — https://arxiv.org/pdf/2605.14976
45. On Regime Switching Models, MDPI — https://www.mdpi.com/2227-7390/13/7/1128
46. Time Varying Transition Probabilities for Markov Regime Switching Models, VU Research Portal — https://research.vu.nl/ws/portalfiles/portal/267687090/Time_Varying_Transition_Probabilities_for_Markov_Regime_Switching_Models.pdf
47. Markov Switching Models: An Example for a Stock Market Index — https://personal.eur.nl/kole/rsexample.pdf
48. Herfindahl-Hirschman Index (HHI), DSP Mutual Fund — https://www.dspim.com/latest-literature/getting-smarter-series-hhi-index.pdf
49. Concentration Risk in Angel Investing: The HHI Score Explained, AngelHub Blog — https://angelhub.app/blog/concentration-risk-hhi-score-explained
50. Herfindahl–Hirschman index, Wikipedia — https://en.wikipedia.org/wiki/Herfindahl%E2%80%93Hirschman_index
51. Herfindahl-Hirschman Index, Antitrust Division, Department of Justice — https://www.justice.gov/atr/herfindahl-hirschman-index
52. Concentration within Sectors and Its Implications for Equal Weighting, S&P Global — https://www.spglobal.com/spdji/en/documents/research/research-concentration-within-sectors-and-its-implications-for-equal-weighting.pdf
53. Marginal Risk Contribution Formula, Quantitative Finance Stack Exchange — https://quant.stackexchange.com/questions/37878/marginal-risk-contribution-formula
54. The Hidden Risk Factor, Journal of Mathematical Finance, SCIRP — https://www.scirp.org/journal/paperinformation?paperid=37587
