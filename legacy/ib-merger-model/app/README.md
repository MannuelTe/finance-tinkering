# Aareland Regionalbank — Swiss M&A Risk Workbench

A Streamlit workbench for a simulated Swiss bank acquisition. Edit the three
banks' loan books, push a macro scenario through them, and read the resulting
risk profile by **client type** (Privatkunden vs Firmenkunden) and by
**region** — then see what that does to each of the two candidate targets,
under Swiss GAAP and Swiss capital rules.

> **All data is fictional.** Aareland Regionalbank, Novafin Kreditbank and
> Banca Alpina do not exist. Every figure is invented for an educational
> simulation. The regulatory commentary is a simplified teaching summary, not
> a statement of Swiss law, and nothing here is financial, legal, tax or M&A
> advice.

## Run it

```bash
pip install -r app/requirements.txt
```

```bash
streamlit run app/streamlit_app.py
```

## The case

**Aareland Regionalbank (A)** — CHF 41bn, Mittelland-centred retail bank.
Mortgage-heavy, deposit-rich, 17.0% CET1. Wants to grow consumer lending.

**Novafin Kreditbank (B)** — CHF 7.2bn consumer credit and card specialist.
High return on equity, wholesale-funded, and sitting at 11.85% CET1 — already
marginally **below its own 12% requirement** on a standalone basis.

**Banca Alpina (C)** — CHF 8.4bn conservative house in Lugano. 20.5% CET1,
heavily over-reserved, and with 64% of its book in Ticino.

## What's in it

| Tab | What it answers |
|---|---|
| **Overview** | Capital against requirement, value adjustments, reserve releases |
| **Client risk profile** | How the shock splits between individuals and companies |
| **Regional exposure** | Where the risk sits across the four regions, and how concentrated |
| **M&A decision** | Pro forma capital and EPS for buying B vs C |
| **Bank data** | Editable product-level book |
| **Swiss rules explained** | What Swiss law changes, in plain English, with a live GAAP comparison |
| **Method** | The transmission chain, written out |
| **Glossary** | All 104 terms in standard English, searchable |

### Controls

Five macro sliders — unemployment, GDP, SNB policy rate, property prices, and
the **Swiss franc**. Seven presets including a **franc shock** modelled on
January 2015. Regional overrides let you shock one region alone; management
levers cover limit increases, book growth and underwriting.

## What Swiss law changes

This is not a relabelling of the Canadian version. Three rules change the
economics rather than the presentation:

**1 · Consumer credit rates are capped (KKG / VKKG).** The Federal Council
sets a ceiling around 12% for consumer credit. The thesis that drives card
lending in unregulated markets — roughly 21% lending against 3% funding, some
eighteen points of gross margin — does not exist here. Card APRs in this model
run 10.9% to 12.9%, so the spread is about a third narrower and the books are
underwritten far more tightly to match.

**2 · Swiss GAAP has no IFRS 9 staging.** Swiss banks book individual value
adjustments as impairment is incurred, plus a provision for inherent default
risks. There is no jump to lifetime expected loss on a forecast, so there is
no stage 1 → 2 cliff. The engine computes the Swiss figure as the headline and
runs an **IFRS 9 shadow alongside it** — the gap widens from +16% at base to
+171% in a severe recession, which is the single clearest illustration of what
the accounting difference actually does.

**3 · Mortgages carry a sectoral capital buffer.** On top of ordinary RWA,
Swiss residential mortgage positions attract a sectoral countercyclical
buffer. A mortgage-heavy target therefore costs more capital than its RWA
implies — the requirement for acquiring C is 13.38% against 13.05% for B,
purely because C brings mortgages.

Plus: **reserves for general banking risks** (an equity reserve with no IFRS
twin, which smooths reported earnings without adding capital), the **1%
issuance duty** on any equity raise, **cantonal tax** at a Zurich rate of
19.7%, and **FINMA plus COMCO approval** as conditions precedent. All are
written out in the "Swiss rules explained" tab.

## Files

```
app/
├── streamlit_app.py   UI
├── engine.py          macro transmission, Swiss GAAP value adjustments, capital
├── merger.py          deal pro forma, sectoral buffer, stamp duty gross-up
├── banks.py           the three banks' static data and portfolios
├── swiss_notes.py     the regulatory commentary rendered in the explainer tab
├── glossary.py        104 terms explained in standard English
├── theme.py           validated chart palette
└── requirements.txt
```

## Glossary

The glossary tab covers three vocabularies that collide in this case:
ordinary banking abbreviations (PD, LGD, EAD, CET1, RWA, CCF, goodwill,
accretion), the German and Italian terms Swiss banking actually runs on
(*Einzelwertberichtigung*, *Kreditfähigkeitsprüfung*, *stille Reserven*,
*Betreibung*, *Grenzgänger*), and the statutes behind them (KKG, VKKG, ERV,
FusG, BankG, FINMA, SNB, IKO, ZEK, esisuisse).

Every entry gives the term, what it stands for, and a plain-English meaning;
where a term is an algebraic identity, the formula is shown. It is searchable,
with a filter for the 36 Swiss-specific entries.

## How the model works

Each exposure line — bank × client type × product × region — runs through:

1. **PD** responds log-linearly to five macro inputs. The franc term is the
   Swiss addition, and commercial lending carries by far the largest franc
   beta: exporters and tourism operators are who a strong franc actually hurts.
2. **LGD** moves with collateral value. Swiss mortgage lending is full
   recourse with mandatory amortisation, so even a property crash moves it
   modestly.
3. **Exposure migrates** as revolvers consume headroom — but less than in an
   unregulated market, because the KKG affordability test already assumed the
   full limit was drawn before it was granted.
4. **Swiss GAAP value adjustments**, with an IFRS 9 shadow for comparison.
5. **Capital**: charges hit CET1 after tax; the requirement is 12.0% of RWA
   plus 2.5% of mortgage RWA.

### Two things that tie exactly, by construction

- **Total RWA** reconciles to each bank's reported figure through a solved
  plug for securities, operational risk and other non-loan assets.
- **Base value adjustments** are calibrated to the carried allowance. The
  calibration factor is itself a diligence signal: **B is 0.82x** (under-
  reserved), against A at 1.23x and **C at 2.68x** — the conservatism that,
  combined with C's general banking risk reserve, suggests its book value
  understates it. That is the *stille Reserven* point arriving as a number.

### Regional design

Four regions, deliberately unequal in how they respond:

| Region | Most sensitive to |
|---|---|
| **Mittelland** | Property prices and rates — highest valuations |
| **Romandie** | The franc and exports — Geneva trading, the Jura watch arc |
| **Alpen** | The franc and employment — tourism, seasonal work |
| **Tessin** | Employment and the franc — cross-border workers, Italian exposure |

A franc shock hits Tessin (+152% expected loss) and the Alpen (+144%) far
harder than the Mittelland (+93%). A Ticino-only shock raises C's value
adjustments by 122% while barely touching A. Concentration shows up as HHI:
A 0.348, B 0.328, **C 0.475** against 0.250 for a perfectly even book.

### Scope

The deal tab is a run-rate model with synergy phase-in on flat underlying
earnings. Cost synergies are set below what a single-language market would
support, because a Swiss retail bank runs documentation, contact centres and
KKG disclosures in three languages.

Transmission coefficients, regional splits and behavioural responses are
invented for this simulation and are not calibrated to any real portfolio.
Read the shape of the answers, not the decimals.
