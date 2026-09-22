# Pricing Workflow and Source-System Map

This reference explains the reviewed A-share OTC option pricer at two levels: the business quote path and the research/model build path. The public demo implements the auditable vanilla core only.

## 1. What the system is

The source application is a self-contained browser pricer aimed at indicative A-share single-stock OTC quotes for Hong Kong clients and banks. It combines:

- trade capture from a short natural-language instruction;
- spot, rate, dividend, stock-borrow, volatility, FX, and correlation inputs;
- three volatility-shape choices: empirical conditional smile, legacy formula, and ML challenger;
- an eSSVI implied-volatility surface with numerical arbitrage diagnostics;
- European Black-Scholes and American CRR valuation;
- local-volatility/Monte Carlo components for path-dependent structures and consecutive-limit-up knockouts;
- local, quanto, and composite settlement;
- Greeks and a dealer quote waterfall containing hedge and balance-sheet reserves;
- source labels, manual marks, peer/event/flow views, and regression checks.

It is not a production-ready system. Several curves are indicative placeholders, the app does not implement trade booking or market-data governance, and key assumptions require independent approval.

## 2. Quote path, step by step

### Step 1: Parse and normalize the trade

The UI recognizes underlying code/name, notional, expiry, call/put, European/American style, strike convention, client side, currency, and settlement type. Strike may be absolute, spot percentage, ATM spot, or ATM forward.

Why it matters: a mathematically correct price for the wrong contract is still wrong. The normalized terms must be shown back to the user before valuation.

### Step 2: Initialize market state

The source system loads spot, a CNY rate, a discrete dividend schedule, a borrow term structure, bid/ask volatility width, credit/capital assumptions, and impact parameters. Per-stock statistics feed the volatility and reserve layers.

Public-demo simplification: every input is supplied by the user. No value is represented as current market data.

### Step 3: Present-value cash dividends

For each dividend paid before expiry:

`PV(div) = sum(D_i exp(-r t_i))`

The reviewed cross-border path applies a withholding-tax haircut to dividends for an offshore holder. In production, declared and forecast dividends need separate provenance and scenario treatment.

### Step 4: Build the equity forward

With discrete dividends and an annualized stock-borrow benefit `b`:

`F = (S - PV(div)) exp((r - b)T)`

The sign is deliberate. A holder can lend stock and receive borrow income; equivalently, a short pays borrow. Higher `b` lowers the forward relative to pure cash-and-carry. This is distinct from a recall/liquidity reserve later in the quote.

For a continuous dividend yield `q`, the analogous expression is `F = S exp((r - b - q)T)`.

### Step 5: Determine strike and log-forward moneyness

The chosen convention is converted to an absolute strike `K`, then:

`k = ln(K/F)`

The surface uses log-forward moneyness, while trader marking pillars may be expressed as percentages of spot. The conversion must use the same forward as the quote.

### Step 6: Establish the volatility level and shape

The source system has three shape engines:

1. **COND**: estimates future-realized-volatility ratios conditional on standardized terminal return buckets. Per-stock estimates shrink toward peer and market panels because individual samples are sparse.
2. **FORM**: a legacy formula based on downside beta, kurtosis, jumps, and limit-up frequency. It is retained as a challenger because empirical work found its skew sign unreliable for the sample.
3. **ML**: a small neural network pretrained on a calibrated synthetic A-share panel and lightly fine-tuned on real observations. It predicts conditional log volatility ratios from stock, index, and moneyness features.

The physical-measure volatility forecast is not directly a tradable implied volatility. The system adds a P-to-Q bridge, applying an index-derived variance-risk premium only to the estimated systematic variance component, plus a skew adjustment.

Public-demo simplification: one flat risk-neutral volatility input. This makes the arithmetic transparent but omits smile and term structure.

### Step 7: Project to eSSVI

Each engine's target smile is fitted to an eSSVI surface. In total-variance form:

`w(k,T) = theta/2 * [1 + rho phi k + sqrt((phi k + rho)^2 + 1 - rho^2)]`

The implementation constrains parameters using Gatheral-Jacquier sufficient conditions, checks Durrleman butterfly density numerically, and checks total variance for calendar monotonicity.

Important: projection residual is model risk. A large residual means the arbitrage-free family cannot reproduce the target shape closely.

### Step 8: Apply manual marks

Traders can override points on a tenor by spot-percentage grid. A Gaussian kernel spreads each change across nearby log-moneyness and log-tenor points, with shrinkage to prevent a single pillar from moving the whole surface.

The reviewed implementation detects arbitrage after overrides but does not automatically repair or reject it. That is a production-control gap.

### Step 9: Add scheduled-event variance

Earnings, unlocks, index reviews, and similar events contribute incremental variance if they fall before expiry:

`sigma_event = sqrt(sigma_base^2 + event_variance/T)`

The reviewed event calendar and shock multipliers are indicative, so they must not be described as observed option-market marks.

### Step 10: Treat cross-currency settlement

- **Local**: price in CNY; the client bears FX separately.
- **Quanto**: lock the conversion rate. The equity drift is adjusted using equity/FX correlation and both volatilities. Correlation convention must be explicit because `CNY per USD` and `USD per CNY` have opposite signs.
- **Composite**: the payoff retains equity and FX exposure. A simplified combined volatility is `sqrt(sigma_S^2 + sigma_FX^2 + 2 rho sigma_S sigma_FX)` under the chosen quote convention.

The source system also adds basis, FX hedge, back-to-back, and correlation reserves. These are commercial adjustments, not part of the vanilla theoretical price.

### Step 11: Convert the forward to a kernel yield

The Black-Scholes kernel expects a continuous carry input. The system solves:

`q0 = r - ln(F/S)/T`

This guarantees that the pricing kernel reproduces the curve-layer forward. Without this bridge, put-call parity can disagree with the displayed forward.

### Step 12: Calculate theoretical value

For a European call:

`C = S exp(-qT) N(d1) - K exp(-rT) N(d2)`

For a European put:

`P = K exp(-rT) N(-d2) - S exp(-qT) N(-d1)`

with `d1 = [ln(S/K) + (r-q+sigma^2/2)T] / (sigma sqrt(T))` and `d2 = d1 - sigma sqrt(T)`.

American exercise uses a Cox-Ross-Rubinstein tree in the source. The public demo intentionally supports European options only.

### Step 13: Calculate risk sensitivities

The source reports Delta, Gamma, Vega, daily Theta, Rho, Vanna, Volga, dividend sensitivity, borrow sensitivity, cash Gamma, and tenor-bucket Vega. Many are bump-and-revalue.

Always state units. In the public demo, Vega and Rho are per one percentage point, and Theta is per calendar day.

### Step 14: Estimate hedge and operational reserves

The reviewed system estimates:

- market-impact cost from hedge size relative to average daily volume;
- short-stock recall/availability reserve for put hedges;
- gap/Gamma exposure associated with daily price limits;
- Stock Connect closed-day mismatch;
- foreign-ownership headroom;
- FX basis, back-to-back, and hedge costs;
- quanto-correlation stress;
- counterparty credit and capital charges.

These formulas are indicative heuristics, not universal valuation identities. They require desk governance and realized-P&L validation.

### Step 15: Form the client quote

For a client purchase, the application adds reserves to theoretical value. For a client sale, it subtracts them subject to a non-negative floor. Premium is represented as a percentage of equity notional and then converted to the settlement currency.

The quote waterfall is the key audit feature: theoretical price and every add-on remain visible rather than being hidden in a single volatility number.

### Step 16: Validate before use

The source tests local/quanto/composite put-call parity, UI rendering, ML forward-pass consistency, simulation stylized facts, and surface arbitrage. A production process additionally needs independent model validation, data lineage, maker-checker approvals, immutable quote records, calibration monitoring, fallback behavior, and P&L attribution.

## 3. Research and model-build path

The Python model pipeline has these stages:

1. **Fetch and normalize data**: daily stock/index series, financing/flow fields, dividends, Stock Connect tags, and FX series.
2. **Calculate analytics**: realized volatilities over several windows, HAR forecasts, jump/limit statistics, betas, correlations, turnover, and peer distances.
3. **Estimate conditional smiles**: bucket future realized volatility by standardized terminal return and shrink sparse stock estimates toward broader panels.
4. **Build the P-to-Q bridge**: compare index conditional realized volatility with ETF option implied marks; transfer only the systematic component to single stocks.
5. **Fit eSSVI**: project target smiles into a common arbitrage-controlled surface representation.
6. **Calibrate the limit-up/limit-down simulator**: reproduce A-share stylized facts including serial limit events, asymmetric volatility response, sectors, and event shocks.
7. **Generate synthetic training panels**: use the calibrated data-generating process to supplement the small real sample.
8. **Train and validate the ML challenger**: pretrain on synthetic panels, tune only on validation partitions, and evaluate once on purged-time and held-out-stock tests.
9. **Export browser weights and scalers**: run the small network client-side, then project its smile through the same eSSVI layer.
10. **Price consecutive-limit-up knockout structures**: derive local variance from the marked surface, add a self-exciting limit-up state, enforce one-step martingale drift, and calibrate relative knockout loss.
11. **Build the self-contained app**: concatenate UI fragments and selected JSON artifacts into one offline HTML file.

## 4. File-level map of the reviewed source

- `src/pricer/a2_eng.html`: Black-Scholes Greeks, event calendar, surface construction, manual marking, arbitrage checks.
- `src/pricer/a3_state.html`: trade state, forward/dividend logic, natural-language parsing.
- `src/pricer/x3_quote.html`: main quote waterfall.
- `src/pricer/x8_cond.html`: conditional engine and spot-percentage marking grid.
- `src/pricer/x9_ko.html`: local-volatility plus self-exciting consecutive-limit-up Monte Carlo.
- `src/pricer/x10_ml.html`: browser ML inference and surface selection.
- `src/pricer/platform.js`: curve, forward, settlement adjustment, surface, and risk-report abstractions.
- `src/pricer/opt_engine.js`: reusable vanilla, CRR, Monte Carlo, snowball, and shark-fin functions.
- `src/engine/essvi.py`: eSSVI fitting and no-arbitrage conditions.
- `src/engine/condvol*.py`, `fitcond2.py`: conditional smile estimation and fitting.
- `src/engine/simpanel.py`, `simcal.py`, `mkdata.py`: synthetic panel generation and calibration.
- `src/engine/train*.py`, `export_ml.py`: ML evaluation and browser export.
- `tests/parity.js`, `tests/regression.js`, `tests/ml_engine.js`: parity, UI, and inference regression checks.

## 5. What the public demo does not implement

It omits live data, per-stock marks, peer models, eSSVI calibration, manual surface overlays, CRR, local volatility, barrier/knockout simulation, ML weights, and detailed dealer reserves. Those omissions are intentional: the demo is a minimal, reproducible illustration of the quote mechanics, not a substitute for the source system or a production pricer.
