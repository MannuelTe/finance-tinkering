# Paper hints: Boukardagha (2026), arXiv:2603.04441

Audit of every arXiv version's source for statements about the unstated parameters.

## Sources examined

- **Versions:** the arXiv abstract page shows **only v1** (submitted Sat 21 Feb 2026 00:33 UTC, 871 KB). `https://arxiv.org/e-print/2603.04441v2` returns an HTML error page, so there is no v2.
- **Saved under `paper_source/`:**
  - `v1_eprint` (the tar.gz), extracted to `v1/`
  - `paper_v1.pdf` and `abs.html`
  - `yahoo_check/`: small scripts and Yahoo JSON used for the reconciliation checks below
- **Contents of `v1/`:**
  - `00README.json`: declares `Exlainable_Trading.tex` as `"usage": "toplevel"` and `main.tex` as `"usage": "ignore"`. That makes `main.tex` an **older draft** that shipped in the bundle but was not compiled.
  - `Exlainable_Trading.tex` (822 lines): the published paper, cited below as **E:line**.
  - `main.tex` (639 lines): the older draft, titled *"Explainable Regime Investing: Parametric vs. Non-Parametric Regime Detection"*, cited below as **M:line**.
  - 13 PNG figures, and no .bib/.aux/.bbl (the bibliography is inline `thebibliography`). There is no code and no data.
  - The tex references `KNN_pnl.png`, `KNN_weights.png` and `KNN_concentration.png`, but the files are named `Knn_*.png`.
- **Legend:**
  - **(a)** explicitly stated in the published text
  - **(b)** implied by comments, the older draft, figures or numerical reconciliation
  - **(c)** nothing said

## 1. Data

| Parameter | What the paper says | Source | Replication (config.py) | Status |
|---|---|---|---|---|
| Source / price field | (a) "daily adjusted close prices from Yahoo Finance" | E:103, M:82 | Yahoo adjusted close | same |
| Date range | (a) "from 2005 to 2026" (published only; the draft has no dates) | E:103 | `data_start=2005-01-01` | same |
| Tickers | (a) labels only: "S&P 500 Index proxy (SPX)", "Broad bond proxy (BOND)", "Gold (GOLD) and Oil (OIL)", "U.S. Dollar proxy (USD)" | E:106-111 | SPY, TLT, GLD, USO, UUP | unstated. (b) See §6: **SPX ≈ `^GSPC` (price index, no dividends)**; **BOND ≈ IEF** (possibly GOVT/LQD); **not TLT**; not AGG/BND |
| Test window | (a) draft: "3-year backtests from 2023 to 2026". (b) Figures start about June 2023 and end about Feb 2026. The published weight tables imply **680 HMM OOS days and 682 KNN days**; the draft implies 677 and 679 | M:303; E:418-422 (Time>10% column = k/680 and k/682) | 2023-06-02 to 2026-02-20 (682) | close. (b) The best benchmark reconciliation is HMM OOS **2023-06-05 to 2026-02-19** (680 sessions). KNN 682 would then start 2023-06-01. The draft's data ended about 2026-02-13 |
| Frequency | (a) daily | E:103 | daily | same |
| Missing data | (c) | – | common panel from 2007-03-01 (UUP) | unstated |
| Total return vs price | (a) "adjusted close". (b) The SPX benchmark matches the **price index `^GSPC`**, not SPY total return (§6) | E:103 | SPY adjusted | (b) different for SPX |
| Returns | (a) log returns, $r_t=\log P_t-\log P_{t-1}$. The portfolio return is $r^p_t = w_t^\top r_t$ (weighted **log** returns) | E:104, E:238, E:270 | log features; portfolio and asset-moment outcomes use **simple** returns (`data.py:38`) | (b) different: paper metrics are on weighted log returns |

## 2. Features

| Parameter | What the paper says | Source | Replication | Status |
|---|---|---|---|---|
| Vector | (a) $x_t=[r_t;\sigma_t;m_t]\in\mathbb R^{3N}$ | E:116-140 | same | same |
| Volatility window | (a) "60-day rolling volatility" | E:126 | 60 | same |
| Momentum window | (a) "20-day rolling mean return" | E:127 | 20 | same |
| Rolling definition | (a) KNN pseudocode: $\sigma_s=\mathrm{Std}(r_{s-w_\sigma+1:s})$, $m_s=\mathrm{Mean}(r_{s-w_m+1:s})$ | E:300-301 | – | same |
| Timing | (a) "All features at time $t$ use information available up to $t-1$". (a) "Let $x_t$ be the most recent feature vector (constructed using data up to $t-1$)" | E:128, E:140, E:303 | uses $t-1$ | same |
| Scaling / standardization | (c) | – | standardized | unstated |

## 3. HMM and order selection

| Parameter | What the paper says | Source | Replication | Status |
|---|---|---|---|---|
| Emission / covariance | (a) Gaussian, $\mathcal N(\mu_{t,k},\Sigma_{t,k})$, full matrix implied by $W_2$ with matrix square roots. The type is never named | E:161, E:172-173 | full | consistent |
| Candidate K | (c) only "$K\in\{K_{\min},\dots,K_{\max}\}$" | E:147, E:153 | 2–6 | unstated. (b) At least 5 templates are used, so $K_{\max}\ge 5$ is plausible |
| Order-selection frequency | (a) "periodically (e.g., weekly)"; "$F_K$ (e.g., weekly)" | E:145, E:233 | **63** | **different**: the paper hints 5 sessions |
| Validation window | (c) "$\mathcal V_t$ ... a recent validation slice"; "last $\lvert\mathcal V\rvert$ points of $\mathcal H_t$" | E:146, E:246 | 126 | unstated |
| Score | (a) sum (not mean) over $\mathcal V_t$ of one-step-ahead predictive log-likelihood | E:149, E:249 | mean over $\mathcal V_t$ | (b) scale differs: a sum makes $\lambda_K$ relatively smaller |
| Complexity penalty | (a) "$\lambda_K>0$ ... (e.g., proportional to $K$ or to the number of free parameters)" | E:155 | 0.002 × q(K) | form hinted, value unstated |
| Refit frequency | (a) The pseudocode refits **every day**: "Fit $K_t$-state Gaussian HMM on $X(\mathcal H_t)$" inside the daily loop | E:255 | **10** | **different** (the paper says daily) |
| Training window | (a) expanding, $\mathcal H_t=\{1,\dots,t-1\}$ ("expanding (rolling) window") | E:133, E:244 | expanding | same |
| Probabilities | (a) "filtered ... $p_{t,k}=P(z_t=k\mid\mathcal F_{t-1})$", which is the one-step predictive | E:163 | predictive | same |
| EM iterations, init, seeds | (c) | – | 50 iterations, seed 7 | unstated |

## 4. Wasserstein templates and moment mapping

| Parameter | What the paper says | Source | Replication | Status |
|---|---|---|---|---|
| Number of templates G | (c) as a number. (b) "Template 2 receives negligible posterior mass ... realized dominant-regime set is $\{0,1,3,4,5\}$", which gives zero-indexed templates 0–5, so **G = 6** | E:492-500 (comments at E:507-508, E:534-535) | 6 | same (b) |
| Matching rule | (a) each component goes to its nearest template by $W_2$ (argmin, collisions allowed); probabilities are summed | E:175-181, E:258-259 | nearest | same |
| Smoothing η | (c) | – | 0.05 | unstated |
| Update input | (a) "template-level component averages ... from assigned components using posterior weights" | E:261 | EWMA | consistent |
| Initialization | (a) "using an initial calibration window" (no length given) | E:240 | – | unstated |
| Feature to asset moments | (a) $\mu_t=\sum_g p_{t,g}\mu_g$, $\Sigma_t=\sum_g p_{t,g}\Sigma_g$ (dimension gap not addressed). (b) "We then estimate conditional moments within the expanding window and plug them into ... MVO". (b) Literature section: "we pair regime-conditioned expected returns with **Ledoit–Wolf covariance shrinkage**" | E:191-194, E:133, E:92 (M:74 same) | posterior-weighted mean; covariance shrunk to diagonal (0.10) | (b) **LW shrinkage** is hinted instead of fixed 0.10 diagonal shrinkage |

## 5. Optimizer

| Parameter | What the paper says | Source | Replication | Status |
|---|---|---|---|---|
| Objective | (a) $\mu^\top w-\gamma w^\top\Sigma w-\tau\lVert w-w_{t-1}\rVert_1$ | E:201, E:267 | same | same |
| γ, τ | (c) | – | 3, 1e-4 | unstated |
| Constraints | (a) $\mathbf 1^\top w=1$, $w\ge0$, $\lVert w\rVert_\infty\le w_{\max}$ (long-only, no leverage) | E:202 | same | same |
| $w_{\max}$ | (c) as a number. (b) **0.60**: the KNN weight plot shows 60/40 corner portfolios, and KNN median $N_{\rm eff}=1.92=1/(0.6^2+0.4^2)$. Pixel-reading HMM weights never exceed about 0.46, so the cap does not bind for the HMM | E:458 (table), `Knn_weights.png` | 0.60 | **same (b), strongly supported** |
| Rebalance | (a) daily ("weights are computed daily") | E:199 | daily | same |
| Initial weights | (a) "$w_{t_0}\leftarrow$ equal-weight (or zeros)". (b) The HMM figure starts at 0.2 each, and the first-day turnover spike is about 0.2 | E:241, `PRD_weights.png`, `PRD_rebalancing.png` | replication day-1 turnover is 0.52 | check the initial $w$ |
| KNN pseudocode remnants | lookback $L$, "rebalance frequency $F{=}5$", "triggers $(\delta_\mu,\delta_\Sigma)$", $\mu_{\rm prev}$, label `alg:knn_mvo_weekly_trigger`. None is used in the loop, and the comment reads "USE USER-PROVIDED KNN PSEUDOCODE (UNCHANGED)" | E:281-287, E:296 | – | vestigial. The observed KNN turnover (94% of days >1%) means it is effectively daily |

## 5b. KNN comparator

| Parameter | What the paper says | Source | Replication | Status |
|---|---|---|---|---|
| Neighbours K | (c) | – | 50 | unstated |
| Features / distance | (a) same $x_t$. (c) no metric or scaling given | E:209-210 | – | unstated |
| Moments | (a) mean of neighbour returns; Ledoit–Wolf covariance | E:213-217, E:307-308 | same | same |
| History | (a) expanding; OOS starts at $t_0+L$ | E:296-297 | – | (b) KNN has 2 more OOS days than the HMM (682 vs 680) |

## 5c. Performance measurement

| Item | What the paper says / implies | Source | Status |
|---|---|---|---|
| Sharpe | (b) **mean/std of daily log returns × √252, risk-free rate 0**. The regime table satisfies Sharpe = AnnMean/AnnVol exactly (e.g. 0.101301/0.053593 = 1.8902). Pooling the five regimes reproduces **HMM Sharpe 2.18** (new) and **2.15** (draft) exactly | E:516-522 | explicit formula (c), implied (b) |
| Implied HMM totals | (b) ann. mean 12.80%, ann. vol 5.87%, cumulative log return **0.345** over 680 days (≈ +41% simple). The figures `PRD_pnl.png` and `benchmark_cum_pnl.png` end at about 0.345 | derived | replication: 53% simple, much higher |
| Sortino | (b) mean / std(negative daily returns) × √252. This reproduces SPX 1.50 and EW 2.26–2.27 (§6) | E:633-635 | (b) |
| Turnover | (a) $\mathrm{TO}_t=\tfrac12\lVert w_t-w_{t-1}\rVert_1$. (b) Turnover statistics use n−1 days (HMM 14.43% = 98/679, 5.15% = 35/679; draft 97/676, 38/676) | E:277, E:379-382 | (b) average turnover = ½ Σ avg\|Δw\| checks: 0.015828/2 = 0.0079 |
| Gross vs net | (c) no realized cost is ever deducted; τ appears only in the objective | – | (b) probably gross |
| Max drawdown | (c) no definition, and **not reproducible**: `^GSPC` wealth MDD over the window is −18.9% vs paper −14.62%; EW gives ≈ −7.7% vs −9.87%. The closest SPX variant is (1+cumlog)/(1+max cumlog)−1 = −15.4% | E:633-635 | unresolved |
| $N_{\rm eff}$ | (a) $(\sum w_i^2)^{-1}$ | E:277 | – |

## 6. Numerical reconciliation (checks with Yahoo data, run 2026-09-30)

- **The draft mislabelled assets; the published version fixed it.** The draft's parametric allocation rows (M:381-385) equal the published rows (E:418-422) under the relabelling draft SPX→GOLD, draft GOLD→OIL, draft OIL→USD, draft USD→SPX, with BOND unchanged. For example, draft "SPX" 0.2169/0.0409/0.9941/0.0039 matches published "GOLD" 0.2239/0.0411/0.9941/0.0039. The asset-Sharpe-by-regime tables permute the same way (regime C: draft SPX/GOLD/OIL/USD 2.40/0.34/−0.33/0.44 matches published GOLD/OIL/USD/SPX 2.52/0.43/−0.40/0.39).
  - This is exactly what happens when yfinance returns columns **alphabetically sorted** and the code labels them in list order [SPX, BOND, GOLD, OIL, USD]. The sorted order must be [gold, bond, oil, usd, spx]. That requires the SPX ticker to sort last (e.g. `^GSPC`, since `^` sorts after letters) and the bond ticker to sort between GLD and USO (IEF, LQD, TLT, TIP, GOVT…, but **not AGG or BND**).
  - Confirmation: the draft's "SPX Buy & Hold" Sharpe/Sortino **1.83/2.20** (M:546) equals **GLD** over the window (computed 1.83–1.84 / 2.20–2.21).
- **SPX benchmark is `^GSPC` price index, log returns, rf = 0.** On 2023-06-05 to 2026-02-19 (680 days): **1.175 / 1.497**, matching the paper's **1.18 / 1.50**. SPY (adjusted) gives 1.24 and VOO gives 1.28. The figure's SPX cumulative log return ends at about 0.475, which is also `^GSPC` (SPY total return would be about 0.51).
- **Equal-weight benchmark is 20% daily rebalanced, the average of log returns.** On the same window:

  | Bond proxy | New Sharpe/Sortino (paper 1.59/2.27) | Draft window (677 d) (paper 1.54/2.19) |
  |---|---|---|
  | IEF | **1.588/2.263** | **1.542/2.184** |
  | GOVT | 1.595/2.250 | 1.549/2.170 |
  | LQD | 1.596/2.246 | 1.550/2.167 |
  | TIP | 1.576/2.216 | 1.531/2.140 |
  | TLT (replication) | 1.430/2.072 | 1.384/1.993 |

  **IEF fits best, and TLT is clearly rejected.**

## 7. All results tables across versions

There is only one arXiv version. The two "versions" of each table are the older draft (`main.tex`, not compiled) and the published file (`Exlainable_Trading.tex`, whose comments read "Updated Table: ... (KNN vs Commercial V2.0 Parametric)").

### OOS performance (KNN vs parametric)

| | Draft M:314-315 | Published E:345-346 |
|---|---|---|
| KNN Sharpe | 1.80 | 1.81 |
| KNN MDD | −12.52% | −12.52% |
| HMM Sharpe | 2.15 | 2.18 |
| HMM MDD | −5.35% | −5.43% |

### Turnover (KNN | HMM)

| Metric | Draft M:344-347 | Published E:379-382 |
|---|---|---|
| Avg daily TO | 0.5665 \| 0.0081 | 0.5665 \| 0.0079 |
| 95% quantile | 1.0000 \| 0.0568 | 1.0000 \| 0.0504 |
| Days >1% | 94.10% \| 14.35% | 94.13% \| 14.43% |
| Days >5% | 93.51% \| 5.62% | 93.54% \| 5.15% |

### Average allocation: Avg Wt / Wt Vol / Time>10% / Avg\|Δw\|

KNN (draft M:381-385, published E:418-422):

| Asset | Draft | Published |
|---|---|---|
| SPX | 0.2224/0.2522/0.4683/0.2416 | 0.2215/0.2520/0.4663/0.2406 |
| BOND | 0.1898/0.2256/0.4595/0.2027 | 0.1907/0.2258/0.4619/0.2033 |
| GOLD | 0.1840/0.2446/0.4035/0.2376 | 0.1846/0.2447/0.4047/0.2381 |
| OIL | 0.2012/0.2383/0.4566/0.2311 | 0.2012/0.2380/0.4575/0.2309 |
| USD | 0.2026/0.2422/0.4566/0.2200 | 0.2020/0.2419/0.4560/0.2201 |

HMM (the draft rows are mislabelled; see §6):

| Asset | Draft (as labelled) | Published |
|---|---|---|
| SPX | 0.2169/0.0409/0.9941/0.0039 | 0.2567/0.1067/0.9368/0.0061 |
| BOND | 0.2419/0.1084/0.9557/0.0018 | 0.2231/0.1043/0.9544/0.0016 |
| GOLD | 0.0050/0.0149/0.0030/0.0019 | 0.2239/0.0411/0.9941/0.0039 |
| OIL | 0.2768/0.0542/1.0000/0.0025 | 0.0043/0.0144/0.0029/0.0017 |
| USD | 0.2594/0.1088/0.9409/0.0063 | 0.2920/0.0495/1.0000/0.0025 |

Implied sample sizes (from the Time>10% fractions): draft KNN 679 / HMM 677; published KNN 682 / HMM 680.

The replication's average HMM weights are SPY 0.446, TLT 0.228, GLD 0.251, USO 0.024 and UUP **0.051**, against the paper's USD **0.292**, held above 10% on 100% of days.

### Concentration

$N_{\rm eff}$ avg/median, KNN 2.07/1.92 and HMM 3.63/3.70, is **identical in both** (M:415-416, E:457-458). It was not updated for the published version.

### Portfolio by regime: Days / AnnMean / AnnVol / Sharpe / Hit / MaxDD

| Regime | Draft M:459-463 | Published E:518-522 |
|---|---|---|
| A | 209/.1327/.0527/2.517/.589/−.0394 | 222/.1013/.0536/1.890/.559/−.0496 |
| B | 32/.2852/.0786/3.630/.594/−.0085 | 29/.3230/.0793/4.072/.621/−.0080 |
| C | 212/.1480/.0615/2.406/.627/−.0294 | 211/.1533/.0612/2.507/.645/−.0289 |
| D | 211/.0737/.0574/1.283/.602/−.0391 | 204/.0963/.0576/1.672/.627/−.0389 |
| E | 13/.1061/.0651/1.630/.615/−.0091 | 14/.2276/.0700/3.251/.643/−.0096 |

Regime E "emerges shortly after Liberation Day" (E:591). There are 6 templates, and template 2 is unused.

### Asset Sharpe by regime: SPX / BOND / GOLD / OIL / USD

| Regime | Draft M:476-480 | Published E:545-549 |
|---|---|---|
| A | 2.21/1.00/−0.66/−0.49/1.93 | 1.87/0.70/1.38/−1.00/−0.02 |
| B | 2.25/4.83/−1.86/−3.48/4.13 | 4.23/3.38/2.60/−1.12/−2.75 |
| C | 2.40/2.83/0.34/−0.33/0.44 | 0.39/2.89/2.52/0.43/−0.40 |
| D | 0.99/−2.49/1.63/3.18/0.71 | 0.77/−2.06/1.27/1.89/2.70 |
| E | 1.38/1.47/−1.71/−0.81/−2.91 | −2.28/0.81/2.28/0.41/0.33 |

### Benchmarks: Sharpe / Sortino / MDD

| Strategy | Draft M:544-546 | Published E:633-635 | Reconciled here |
|---|---|---|---|
| HMM | 2.16 / 2.79 / – | 2.18 / 2.82 / −5.43% | Sharpe exact from regime table |
| Equal weight | 1.54 / 2.19 / – | 1.59 / 2.27 / −9.87% | IEF: 1.54/2.18 and 1.59/2.26 |
| SPX | **1.83 / 2.20** / – | 1.18 / 1.50 / −14.62% | draft = GLD; published = `^GSPC` |

- The draft's HMM Sharpe is internally inconsistent: 2.15 in the performance table vs 2.16 in the benchmark table.
- The abstract and introduction (E:26, E:56) repeat 2.18 / 1.59 / 1.18 and −5.43% / −14.62%.

### "Commercial V2.0 Parametric"

- It appears only in LaTeX comments above the updated tables (E:335, E:369, E:405, E:447).
- The draft introduces the parametric section as "a **commercialization-oriented redesign** of our daily regime-aware allocation framework ... replacing discrete regime-emergence rules and combinatorial label-matching mechanisms" (M:112-114). V1 was therefore presumably an R2-RD-style model (one-time BIC, emergence-only, assignment matching; Hirsa et al. 2024, E:83), and "V2.0" is the Wasserstein-template version.
- The name implies proprietary production code that was never released. Between the draft and the published tables, the V2.0 run also changed: 3 more days of data, and the asset-label bug was fixed.

## 8. Most useful hints for narrowing the unstated parameters

1. **Data:** switch SPX to **`^GSPC` (price index)** and BOND to **IEF**. This reproduces the published SPX (1.18/1.50) and EW (1.59/2.27) Sharpe/Sortino, and the draft's EW 1.54/2.19. TLT and SPY do not. Both proxies sort into the order that explains the draft's label bug.
2. **Window:** the HMM OOS is **680 sessions, ≈ 2023-06-05 to 2026-02-19**; KNN is 682 sessions (2 earlier start days). The data probably ends 2026-02-19, not 02-20.
3. **Metrics:** use daily **log** portfolio returns $w^\top r$, rf = 0, √252; Sortino = mean/std(negative returns). The target HMM cumulative log return is **0.345** (ann. mean 12.8%, vol 5.87%). Pooling the regime table reproduces 2.18 exactly. MDD definitions remain unreconciled.
4. **$w_{\max}=0.60$ is confirmed** by the KNN 60/40 corners (median $N_{\rm eff}$ 1.92).
5. **Target HMM allocation profile:** SPX 0.26, BOND 0.22, GOLD 0.22, OIL ≈ 0, USD 0.29. USD and GOLD stay above 10% almost always. Average TO is 0.0079, and TO is exactly 0 on most days (only 14.4% of days exceed 1%), which points to a meaningful τ and/or very stable moments. This is a strong fingerprint for tuning γ, τ and η; the replication's UUP 5% vs 29% is the biggest mismatch.
6. **Schedule:** the paper indicates **daily refits** and **weekly (≈5-day) order selection**; the replication uses 10 and 63. G = 6 templates is implied (indices 0–5, one unused), and at least 5 of them receive mass.
7. **Covariance:** Ledoit–Wolf shrinkage is hinted for the regime covariance too (E:92), not fixed diagonal shrinkage.
8. **Initial weights:** equal weight at $t_0$ (first-day TO ≈ 0.2 in the figure; the replication's is 0.52).
9. **Nothing anywhere** gives K range, validation length, λ_K value, η, EM iterations/init/seeds, γ, τ, KNN K, feature scaling or cost deductions.
