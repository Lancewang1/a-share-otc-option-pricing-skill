---
name: a-share-otc-option-pricing
description: Explain, demonstrate, review, or sanity-check A-share OTC equity-option pricing, including forwards with dividends and borrow, volatility surfaces, Black-Scholes/CRR valuation, Greeks, cross-currency adjustments, quote reserves, and model-risk controls. Use for educational or indicative pricing work; do not present outputs as executable dealer quotes or investment advice.
---

# A-Share OTC Option Pricing

Use this skill to turn trade terms and market assumptions into an auditable indicative quote, or to explain and review an existing pricing workflow.

## Route the task

- For a quote or numerical example, run `scripts/price_demo.py`. State every assumption and distinguish market inputs, model outputs, and commercial reserves.
- For an end-to-end explanation, read [references/pricing-workflow.md](references/pricing-workflow.md). For Chinese output, read [references/pricing-workflow.zh-CN.md](references/pricing-workflow.zh-CN.md) instead.
- For model review, production-readiness, validation, or limitations, also read [references/model-risk.md](references/model-risk.md).
- For an interactive example, open `assets/demo.html` locally. It is a transparent teaching tool, not the original internal dealer application.

## Quoting workflow

1. Normalize the contract: underlying, call/put, European/American, strike, expiry, notional, side, and settlement currency/type.
2. Establish the valuation date and inputs. Never silently replace missing spot, rates, dividends, borrow, volatility, FX volatility, or correlations with live-market claims.
3. Build the equity forward. For discrete dividends and stock-borrow benefit use `F = (S - PV(dividends)) exp((r - b)T)`. Explain the sign of `b`.
4. Convert the forward into the continuous-yield input required by the pricing kernel: `q0 = r - ln(F/S)/T`.
5. Select the volatility input. A flat volatility is acceptable only for a demo. A real workflow needs a marked, arbitrage-checked surface and explicit provenance.
6. Apply settlement treatment: local, quanto drift adjustment, or composite volatility. Do not confuse these structures.
7. Price with Black-Scholes for European vanilla options or a suitable tree/PDE for American exercise. Report units for all Greeks.
8. Separate theoretical value from hedge, liquidity, credit, capital, FX, correlation, and bid/ask reserves.
9. Run sanity checks: intrinsic/upper bounds, put-call parity, monotonicity, non-negative volatility, and surface butterfly/calendar checks when a surface is used.
10. Label the result `INDICATIVE` unless the user supplies governed market data, approved models, operational controls, and execution authority.

## Demo commands

```bash
python scripts/price_demo.py
python scripts/price_demo.py --spot 100 --strike 105 --days 90 --vol 0.28 --borrow-bps 350 --dividend 1.20 --put --json
```

The script uses only the Python standard library. Treat its flat-volatility and simplified reserve inputs as an inspectable baseline, not a production calibration.

## Non-negotiable distinctions

- Historical/forecast volatility is under the physical measure; an option quote needs a risk-neutral volatility mark or a documented P-to-Q bridge.
- Borrow in the forward and borrow-recall/liquidity reserve are different. Do not charge the full borrow cost twice.
- Synthetic/training data may form a prior, but validation metrics must be reported on real held-out observations.
- Detecting arbitrage is not the same as repairing it. Manual surface overrides can reintroduce violations.
- A public demo must not include proprietary observations, model weights, credentials, or redistributable market data without permission.
