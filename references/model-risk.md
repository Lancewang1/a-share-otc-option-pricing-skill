# Model Risk and Validation Guide

Read this reference when reviewing assumptions, approving a change, or deciding whether a result is fit for use.

## Critical limitations found in the reviewed system

1. **Indicative curves**: rates, dividends, and especially stock borrow are placeholders. Borrow is a first-order long-dated input after the forward-sign correction.
2. **P-to-Q uncertainty**: single-stock implied volatility is not directly observable for unlisted OTC names. The bridge from realized forecasts and ETF options is a model assumption.
3. **Sparse limit-event data**: consecutive limit-ups are rare. Per-stock estimates are unstable and depend on panel shrinkage.
4. **Synthetic-data dependence**: the ML engine relies on a calibrated simulator. Misspecified synthetic dynamics can produce confident but wrong priors.
5. **Surface override risk**: manual marks are checked but not automatically projected back into the no-arbitrage region.
6. **Long-dated knockout instability**: a single diffusion scale cannot reproduce the marked vanilla price under bounded daily returns and self-exciting limits. Relative-loss quoting is only a workaround.
7. **Incomplete operations**: suspension, corporate actions, financing spread, XVA, full bucketed Vega, and trade lifecycle controls are absent or incomplete.
8. **Reserve heuristics**: impact, gap, ownership, correlation, credit, and capital add-ons have not been validated against realized quote P&L in the supplied material.

## Minimum numerical checks

- Reject non-positive spot, strike, time, or volatility.
- Enforce dividend PV below spot for the discrete-dividend forward.
- Check call and put bounds under the same carry assumptions.
- Check put-call parity to a documented tolerance.
- Bump spot and volatility to confirm expected monotonicity and finite Greeks.
- For surfaces, check non-negative total variance, Durrleman density, and calendar monotonicity over a grid wider than quoted strikes.
- For Monte Carlo, report seed, paths, time steps, standard error, convergence, and martingale error.
- For American options, demonstrate tree convergence as steps increase.

## Data and ML controls

- Record source, timestamp, currency, units, adjustment convention, and licensing for every input.
- Keep training, validation, and test partitions immutable; purge overlapping forward windows.
- Evaluate both held-out time periods and held-out underlyings.
- Report performance on real data separately from synthetic data.
- Compare against simple baselines, including constant, bucketed, and shallow-tree models.
- Monitor drift in features, residuals, arbitrage-projection distance, and hedge P&L.
- Keep a challenger and a deterministic fallback available.

## Production gate

Do not call the output executable or fair value until all of the following exist: governed market data, an approved calibration policy, independent validation, maker-checker controls, quote versioning, immutable audit records, fallback behavior, limit monitoring, corporate-action handling, and legal approval for data/model distribution.

## Interpretation discipline

- `INDICATIVE` means a scenario under stated assumptions, not a market quote.
- Model price and client price are different: the latter includes desk-specific reserves.
- A good in-sample surface fit does not establish hedging performance.
- No-arbitrage constraints prevent some internal inconsistencies; they do not prove the model is economically correct.
