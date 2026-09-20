# Financial Mathematics of the Tradebot

> **Abstract.** This note gives a visual mathematical introduction to a constant-weight,
> multi-currency ETF portfolio with a volatility-aware SPY close-to-next-open sleeve. It develops
> currency conversion, portfolio returns, maximum-likelihood estimation, realized variance,
> fractional-Kelly-style sizing, performance measurement, microstructure statistics, and
> dependent-data bootstrap inference. Graphs are placed beside the concepts they illuminate,
> including cumulative wealth, rolling Sharpe ratios, drawdowns, volatility-conditioned decisions,
> sleeve contribution, and parameter sensitivity. A final numerical example amalgamates the
> methods. The historical figures describe one short research sample; they are not investment
> advice or evidence of future returns.

## The mathematics in brief

**Currency conversion.** A price quoted in $Q_i$ is converted to base currency $B$ via

$$P_{i,t}^{B}=\frac{P_{i,t}^{Q_i}}{X_t^{B,Q_i}}.$$

**Portfolio and target sizing.** Net asset value and the ideal target quantity for weight $w_i$ are

$$V_t=C_t+\sum_{i=1}^{m}q_{i,t}P_{i,t}^{B}, \qquad q_{i,t}^{\star}=\frac{w_iV_t}{P_{i,t}^{B}}.$$

**Returns and wealth.**

$$r_t=\frac{P_t}{P_{t-1}}-1,\qquad \ell_t=\log(1+r_t),\qquad V_T=V_0\prod_{t=1}^{T}(1+r_t).$$

**Performance.** Annualized Sharpe ratio and maximum drawdown, with running peak $M_t$:

$$\widehat{S}=\frac{\bar r}{\widehat{\sigma}_{r}}\sqrt{A},\qquad D_t=\frac{V_t}{M_t}-1,\quad D_{\max}=\min_{0\le t\le T}D_t.$$

**Overnight entry filter.** With Gaussian maximum-likelihood estimates $\widehat\mu,\widehat\sigma_{\mathrm{ON}}$
of the overnight return, round-trip cost $c$, and threshold $z\ge 0$, the SPY slice is held overnight when

$$\widehat{\mu}-c>z\,\frac{\widehat{\sigma}_{\mathrm{ON}}}{\sqrt n}.$$

**Conservative variance and fractional-Kelly sizing.** Using the largest of the overnight, daily and
intraday realized-variance estimates,

$$\widehat v_t=\max(\widehat{\sigma}_{\mathrm{ON}}^2,\ \widehat{\sigma}_{\mathrm{D}}^2,\ \widehat v_t^{\mathrm{ID}}).$$

The Kelly-style approximation for the optimal fraction is

$$f^{\star}\approx\frac{\mathbb E[R]}{\mathrm{Var}(R)}.$$

The position fraction is then $\min(f_{\max},\ \lambda(\widehat\mu-c)/\widehat v_t)$ with $\lambda=0.25$.

## Read the full paper

- 📄 [PDF](financial_mathematics_of_tradebot.pdf)
- 🧾 [LaTeX source](financial_mathematics_of_tradebot.tex)

> **Research software, not investment advice.** Nothing here has been validated for live capital.
