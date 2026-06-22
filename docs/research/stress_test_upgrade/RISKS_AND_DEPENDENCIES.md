# RISKS AND DEPENDENCIES

## 1. Data Availability & Quality Risks
- **Risk:** Indian small-cap equities often have highly asynchronous trading and NaN values for bid-ask spreads or volumes.
- **Mitigation:** The Vasicek shrinkage algorithm gracefully defaults to sector means when standard errors are massive. Provide robust fallback defaults (e.g., global median spread) if real-time spread data fails.

## 2. Computational Overhead
- **Risk:** Calculating large covariance matrices ($N \times N$) in real-time during an HTTP request will cause severe latency and timeout errors.
- **Mitigation:** The architecture mandates a nightly batch job (`TASK-04`) to pre-calculate and cache $\Sigma_{normal}$ and $\Sigma_{crisis}$. The inference API only performs matrix multiplication, taking $O(K^3)$ operations.

## 3. Mathematical Instability
- **Risk:** $\Sigma_{11}$ matrix inversion during conditional shock propagation might fail if the matrix is singular or non-positive definite.
- **Mitigation:** Implement eigenvalue clipping (Ledoit-Wolf shrinkage) or diagonal loading to ensure matrices are strictly positive definite before inversion.

## 4. Upstream Dependencies
- Requires `yfinance` or `NSE` endpoints to be perfectly reliable for the nightly ETL. If the ETL fails, the stress engine must fallback to the previous day's cached matrices.
