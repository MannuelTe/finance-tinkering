"""Glossary of every term the app uses, explained in standard English.

Covers three vocabularies that collide in this case: ordinary banking
abbreviations, the German and Italian terms Swiss banking runs on, and the
statutes behind them. Where an entry cites a figure it refers to this
simulation.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Term:
    term: str
    expansion: str          # what the letters or the German stand for
    meaning: str            # plain English
    formula: str = ""       # where the term is an identity
    swiss: bool = False     # Swiss-specific, flagged in the UI


# --------------------------------------------------------------------------
SWISS_LAW = [
    Term("FINMA", "Swiss Financial Market Supervisory Authority",
         "The Swiss financial regulator. Unlike Canada or the UK, Switzerland "
         "does not split prudential supervision from conduct supervision into "
         "two agencies — FINMA does both. It authorises banks, sets capital "
         "expectations, and has to approve anyone acquiring a significant "
         "stake in a Swiss bank.", swiss=True),
    Term("SNB", "Swiss National Bank",
         "Switzerland's central bank. Sets the policy interest rate, and is "
         "the institution that abandoned the euro floor in January 2015 — the "
         "event the franc shock preset is modelled on.", swiss=True),
    Term("KKG", "Konsumkreditgesetz — Federal Act on Consumer Credit",
         "The statute governing consumer lending in Switzerland. Two things in "
         "it drive this whole model: it caps the interest rate that may be "
         "charged, and it requires a formal affordability assessment before "
         "credit is granted or a limit raised. Breaching the affordability "
         "rules costs the lender not just the interest but the credit amount "
         "itself.", swiss=True),
    Term("VKKG", "Verordnung zum Konsumkreditgesetz",
         "The ordinance under the KKG. This is where the actual maximum "
         "interest rate is set — currently in the region of 12% for cash "
         "credit, slightly higher for card overdrafts. It moves with reference "
         "rates, so the ceiling is not a fixed number.", swiss=True),
    Term("Kreditfähigkeitsprüfung", "Affordability / capacity-to-repay assessment",
         "The mandatory check a Swiss lender must run before granting consumer "
         "credit. Two features make it unusually strict: affordability is "
         "tested as if the credit were repaid within 36 months regardless of "
         "the actual term, and for a card or overdraft it assumes the customer "
         "draws the entire limit. A lender cannot treat unused headroom as "
         "costless — which is the legal answer to the exposure-migration "
         "problem this case is built around.", swiss=True),
    Term("IKO", "Informationsstelle für Konsumkredit",
         "The Swiss consumer credit register. Lenders must report consumer "
         "credits and card limits to it, so an assessor can see an applicant's "
         "commitments across the whole market rather than only its own.",
         swiss=True),
    Term("ZEK", "Zentralstelle für Kreditinformation",
         "The Swiss credit bureau, through which banks share credit "
         "information. Together with the IKO register it closes the gap that "
         "makes bust-out fraud viable elsewhere — you cannot quietly build "
         "clean histories at five issuers at once.", swiss=True),
    Term("Betreibung", "Debt enforcement proceedings",
         "The Swiss legal process for collecting an unpaid debt. It is "
         "creditor-friendly and reasonably quick, which is a large part of why "
         "Swiss recovery rates are better — and loss given default lower — "
         "than in many comparable markets.", swiss=True),
    Term("BankG", "Bankengesetz — Banking Act",
         "The statute that authorises and governs Swiss banks. It is the "
         "source of the requirement that FINMA approve anyone acquiring a "
         "qualified participation in a bank, which makes regulatory clearance "
         "a condition precedent to any deal here.", swiss=True),
    Term("FusG", "Fusionsgesetz — Merger Act",
         "The statute setting the corporate mechanics of mergers, demergers, "
         "conversions and asset transfers in Switzerland. It governs how the "
         "transaction is executed, as distinct from whether the regulator "
         "permits it.", swiss=True),
    Term("KG / COMCO / WEKO", "Kartellgesetz — Cartel Act; Competition Commission",
         "Swiss competition law and the authority that enforces it. Mergers "
         "above certain size thresholds must be notified before completion. "
         "For banks the Act measures size differently from ordinary turnover, "
         "and where FINMA judges a transaction necessary to protect creditors, "
         "the prudential interest can override the competition analysis.",
         swiss=True),
    Term("OR", "Obligationenrecht — Swiss Code of Obligations",
         "Swiss contract and company law, including the general accounting "
         "rules that sit underneath the bank-specific ones. It is the source "
         "of the conservative-valuation principle that permits undisclosed "
         "reserves.", swiss=True),
    Term("esisuisse", "Swiss deposit protection scheme",
         "Protects deposits up to CHF 100,000 per depositor per bank. Two "
         "features matter: the scheme has a ceiling on total payout, and it is "
         "funded by surviving banks rather than pre-funded. A large, granular "
         "retail deposit base is therefore genuinely valuable — it is funding "
         "that does not run.", swiss=True),
    Term("Emissionsabgabe", "Federal issuance stamp duty",
         "A 1% federal tax on newly created equity, above a small exemption. "
         "Its abolition was rejected at referendum in 2022, so it still "
         "applies — which means an acquirer that must issue shares to restore "
         "its capital ratio pays for the privilege.", swiss=True),
    Term("Verrechnungssteuer", "Federal withholding tax",
         "35% withholding on interest from bonds issued by Swiss issuers, and "
         "on dividends. Foreign investors can often reclaim it under a treaty, "
         "but the friction is real and is a standing reason Swiss groups have "
         "issued debt through foreign vehicles.", swiss=True),
    Term("SARON", "Swiss Average Rate Overnight",
         "The Swiss franc reference interest rate, successor to CHF LIBOR. It "
         "is the benchmark that floating-rate Swiss lending and the statutory "
         "consumer credit ceiling are referenced to.", swiss=True),
    Term("Swiss finish", "—",
         "Market shorthand for Switzerland deliberately setting capital "
         "requirements above the international Basel minimums. It is why Swiss "
         "banks run CET1 ratios that look generous next to North American "
         "peers — that is the regime working, not spare capital.", swiss=True),
    Term("FINMA categories 1–5", "Supervisory categories",
         "FINMA sorts banks by size and risk into five categories, with 1 the "
         "largest. The category drives how much capital buffer a bank must "
         "hold and how intensively it is supervised. In this case the acquirer "
         "is category 3 and both targets are category 4.", swiss=True),
    Term("TBTF", "Too Big To Fail regime",
         "The separate, much heavier set of capital and resolution "
         "requirements applied to systemically important Swiss banks. None of "
         "the three banks here is systemically important, so it does not bite "
         "— but a large enough merger could eventually raise the question.",
         swiss=True),
    Term("Kantonalbank", "Cantonal bank",
         "A bank owned by a canton, most carrying a cantonal guarantee on "
         "their liabilities. That guarantee lowers funding costs, and it also "
         "makes them awkward acquisition targets, since they are creatures of "
         "cantonal law rather than ordinary companies.", swiss=True),
    Term("Grenzgänger / frontalieri", "Cross-border workers",
         "People living in neighbouring countries and working in Switzerland. "
         "They matter for Ticino in particular, where the local labour market "
         "and the Italian economy are tightly coupled — which is why the "
         "Tessin region carries the highest employment sensitivity in this "
         "model.", swiss=True),
]

# --------------------------------------------------------------------------
SWISS_ACCOUNTING = [
    Term("Swiss GAAP (banks)", "RelV-FINMA and FINMA Circular 2020/1",
         "The accounting framework Swiss banks report under. The critical "
         "difference from IFRS: there is no three-stage expected credit loss "
         "model. Losses are recognised as they are incurred on identified "
         "exposures, plus a broader provision for inherent risk — so "
         "provisions arrive later and more gradually than under IFRS 9.",
         swiss=True),
    Term("Einzelwertberichtigung", "Individual value adjustment",
         "A provision booked against a specific exposure that has actually "
         "deteriorated. The Swiss equivalent of a specific impairment. It is "
         "backward-looking by design: something identifiable has gone wrong.",
         swiss=True),
    Term("Wertberichtigung für inhärente Ausfallrisiken",
         "Value adjustment for inherent default risks",
         "A provision held across the performing book for losses that are "
         "statistically present but not yet identified in any particular loan. "
         "It is the closest Swiss GAAP comes to a forward-looking reserve, and "
         "it moves far more slowly than IFRS 9 staging.", swiss=True),
    Term("Gefährdete Forderungen", "Impaired receivables",
         "Loans where recovery of principal or interest is doubtful. The share "
         "of the book sitting here drives the individual value adjustment. In "
         "this model it is the 'impaired share' column of the bank data tab.",
         swiss=True),
    Term("Reserven für allgemeine Bankrisiken", "Reserves for general banking risks",
         "An explicit equity reserve funded out of profits in good years and "
         "released when conditions turn. It counts as CET1 capital and has no "
         "IFRS equivalent. It does not create capital — the money is inside "
         "CET1 either way — but releasing it offsets the provision charge, so "
         "reported earnings can look untouched in a year when capital actually "
         "fell.", swiss=True),
    Term("Stille Reserven", "Undisclosed / hidden reserves",
         "Assets deliberately carried below their realistic value, which Swiss "
         "statutory accounting has long permitted. Disclosure has tightened, "
         "but the principle survives. For an acquirer it inverts the usual "
         "worry: the target may be worth *more* than its balance sheet admits, "
         "and the seller knows it.", swiss=True),
    Term("IFRS 9", "International Financial Reporting Standard 9",
         "The international standard Swiss banks do *not* use for statutory "
         "reporting. It sorts loans into three stages and forces a jump to "
         "lifetime expected loss when credit risk rises materially — before "
         "any payment is missed. The app runs it as a shadow calculation so "
         "the difference is visible."),
    Term("Stage 1 / 2 / 3", "IFRS 9 impairment stages",
         "Stage 1 is performing, reserved for losses expected in the next 12 "
         "months. Stage 2 means credit risk has risen significantly and the "
         "reserve jumps to cover the loan's whole remaining life. Stage 3 is "
         "credit-impaired. The step from 1 to 2 is a cliff, not a slope — and "
         "it is exactly what Swiss GAAP does not have."),
    Term("ECL", "Expected Credit Loss",
         "The reserve IFRS 9 requires: a probability-weighted loss estimate "
         "built from PD, LGD and EAD."),
    Term("Value adjustments", "Wertberichtigungen",
         "The Swiss GAAP umbrella term for loan loss provisions, covering both "
         "individual adjustments on impaired exposures and the inherent-risk "
         "provision on the performing book. Where a North American report says "
         "'allowance', a Swiss one says this.", swiss=True),
    Term("Reserve adequacy", "Carried allowance ÷ modelled requirement",
         "How the app compares each bank's actual reserve against what its own "
         "model says the book needs. Below 1.0 means thin reserves; well above "
         "1.0 means conservatism, which in Switzerland often signals hidden "
         "value rather than waste.",
         "Adequacy = Carried allowance ÷ Modelled value adjustment"),
]

# --------------------------------------------------------------------------
CAPITAL = [
    Term("CET1", "Common Equity Tier 1",
         "The highest-quality capital: common shares plus retained earnings, "
         "less deductions such as goodwill. This is what absorbs losses first "
         "and without argument, so it is the number regulators care about "
         "most."),
    Term("CET1 ratio", "—",
         "The headline solvency measure — capital divided by risk-weighted "
         "assets.",
         "CET1 ratio = CET1 capital ÷ RWA"),
    Term("RWA", "Risk-Weighted Assets",
         "Assets rescaled by how risky they are before being compared against "
         "capital, so CHF 100 of government bonds and CHF 100 of card debt do "
         "not count the same.",
         "RWA = Σ (Exposure × Risk weight)"),
    Term("Risk weight", "—",
         "The scaling percentage itself. Swiss mortgages sit around 40% here "
         "rather than the 35% Basel standard figure, because of the Swiss "
         "finish and loan-to-value add-ons. Card balances run 45% for people "
         "who pay in full and 75% for those who carry debt."),
    Term("ERV", "Eigenmittelverordnung — Capital Adequacy Ordinance",
         "The Swiss implementation of the Basel capital rules, including the "
         "national add-ons that make up the Swiss finish.", swiss=True),
    Term("CCyB (sectoral)", "Antizyklischer Kapitalpuffer — countercyclical capital buffer",
         "Switzerland runs a countercyclical buffer aimed specifically at "
         "residential mortgages rather than the balance sheet as a whole. It "
         "was reactivated in 2022. Because Swiss retail banks are mortgage "
         "lenders first, it means a mortgage-heavy bank needs materially more "
         "capital than its headline RWA suggests.",
         "Required CET1 = 12.0% × RWA + 2.5% × mortgage RWA", swiss=True),
    Term("CCF", "Credit Conversion Factor",
         "The fraction of an undrawn commitment that must be treated as though "
         "already lent, for capital purposes. Cancellable card lines carry "
         "10%. The app also tracks an *effective* CCF — what a lender would "
         "actually model — and reports the gap.",
         "Capital-relevant exposure = Drawn + (Undrawn × CCF)"),
    Term("Leverage ratio", "—",
         "Capital over total assets with no risk weighting at all. A "
         "deliberate backstop: it cannot be gamed by arguing your assets are "
         "safer than they look.",
         "Leverage ratio = Capital ÷ Total assets"),
    Term("Basel III", "—",
         "The international rulebook for how much capital banks must hold, "
         "written after the 2008 crisis. Switzerland implements it through the "
         "ERV and then adds to it."),
    Term("Capital surplus", "—",
         "How much CET1 a bank holds above its requirement. In this app the "
         "requirement includes the sectoral mortgage buffer, so surplus can be "
         "negative even at a CET1 ratio that looks healthy in isolation."),
]

# --------------------------------------------------------------------------
CREDIT_RISK = [
    Term("PD", "Probability of Default",
         "The chance a borrower stops paying within a stated window. Always "
         "attached to a horizon — a 12-month PD and a lifetime PD are "
         "different numbers for the same person."),
    Term("LGD", "Loss Given Default",
         "Of the amount owed when default happens, the fraction never "
         "recovered. Swiss mortgage LGD is around 11–12% because lending is "
         "full recourse with mandatory amortisation and enforcement is "
         "creditor-friendly. Unsecured card LGD runs about 66–74%.",
         "LGD = 1 − Recovery rate"),
    Term("EAD", "Exposure at Default",
         "How much is actually owed at the moment of default. On a card this "
         "is neither today's balance nor the full limit — it is whatever has "
         "been drawn by then, which tends to be higher than average because "
         "people borrow more as their situation worsens."),
    Term("EL", "Expected Loss",
         "Three numbers multiplied. Because they multiply, an error in any one "
         "scales the whole answer.",
         "EL = PD × LGD × EAD"),
    Term("Exposure migration", "—",
         "The pattern where borrowers consume available credit as they "
         "approach default, so exposure is largest exactly when it is most "
         "likely to be lost. Swiss law blunts this: the KKG affordability test "
         "already assumed the full limit was drawn before granting it."),
    Term("DPD", "Days Past Due",
         "How far behind a borrower is. 30+ means a month late; 90+ means "
         "three months, the conventional definition of default."),
    Term("NCO", "Net Charge-Off",
         "Debt written off as uncollectible, less later recoveries, as a "
         "percentage of the book. The loss that actually happened, against the "
         "loss that was predicted."),
    Term("Allowance", "Loss reserve",
         "Money already set aside against losses not yet realised. In Swiss "
         "reporting this appears as value adjustments."),
    Term("PCL", "Provision for Credit Losses",
         "The annual expense recorded for loans expected to go bad. It builds "
         "the allowance; charge-offs draw it down."),
    Term("Adverse selection", "—",
         "The people most eager to take what you are offering are "
         "disproportionately the ones you would least want to give it to — and "
         "they reveal that only after you have granted it."),
    Term("Bust-out fraud", "—",
         "Behave impeccably for months to earn a limit increase, draw "
         "everything at once across every card, disappear. The IKO and ZEK "
         "registers make this much harder in Switzerland, because a lender can "
         "see commitments across the whole market."),
    Term("Concentration / HHI", "Herfindahl-Hirschman Index",
         "A measure of how unevenly exposure is spread. Sum the squared shares "
         "of each region. With four regions, 0.250 is perfectly even and 1.0 "
         "is everything in one place. Banca Alpina sits at 0.475.",
         "HHI = Σ (share of region i)²"),
]

# --------------------------------------------------------------------------
EARNINGS = [
    Term("NII", "Net Interest Income",
         "Interest earned minus interest paid. The core of banking in one "
         "subtraction.",
         "NII = Interest income − Interest expense"),
    Term("NIM", "Net Interest Margin",
         "The same idea as a percentage, so banks of different sizes compare.",
         "NIM = NII ÷ Earning assets"),
    Term("Spread", "—",
         "Lending rate minus funding cost — gross margin before losses and "
         "overhead. The Swiss point: with consumer rates capped near 12% and "
         "funding under 1%, the card spread is roughly eleven points, against "
         "eighteen in an uncapped market."),
    Term("Funding cost", "—",
         "What the bank pays for the money it lends out. Deposit-rich Swiss "
         "banks fund at 60–75 basis points; the wholesale-funded card "
         "specialist pays 185."),
    Term("ROE", "Return on Equity",
         "What the owners earn on their stake. Thin equity mechanically "
         "inflates it, so a high figure can signal leverage rather than skill.",
         "ROE = Net income ÷ Equity"),
    Term("ROA", "Return on Assets",
         "Earnings per franc of balance sheet, regardless of funding.",
         "ROA = Net income ÷ Total assets"),
    Term("Efficiency ratio", "Cost-to-income ratio",
         "Operating cost per franc of revenue. Despite the name, lower is "
         "better. Swiss banks running three language regions carry structurally "
         "higher costs.",
         "Efficiency ratio = Operating expense ÷ Revenue"),
    Term("Interchange", "—",
         "The fee the merchant's side pays the card issuer on each purchase. "
         "It carries no credit risk — you collect it whether or not the "
         "customer ever borrows."),
    Term("bps", "Basis points",
         "One hundredth of a percentage point. Used because percentages of "
         "percentages are ambiguous.",
         "1 bp = 0.01%   ·   100 bps = 1 percentage point"),
    Term("CAGR", "Compound Annual Growth Rate",
         "The constant yearly rate that would turn the starting value into the "
         "ending one.",
         "CAGR = (End ÷ Start)^(1/years) − 1"),
]

# --------------------------------------------------------------------------
DEAL = [
    Term("M&A", "Mergers & Acquisitions",
         "Buying, selling or combining whole companies. This case is an "
         "acquisition: one bank buys another and keeps control."),
    Term("Goodwill", "—",
         "The part of the price not matched by identifiable net assets — "
         "brand, customer relationships, expected synergies. It lands on the "
         "buyer's balance sheet as an asset, but regulators deduct it straight "
         "back out of capital, so a high premium costs capital twice.",
         "Goodwill = Price paid − Net assets acquired"),
    Term("Book value", "Equity, net worth",
         "What is left for the owners once every liability is subtracted from "
         "every asset. In Switzerland, watch for hidden reserves — reported "
         "book value may understate the real figure.",
         "Book value = Total assets − Total liabilities"),
    Term("P/B", "Price-to-Book ratio",
         "Purchase price divided by book value, read as francs paid per franc "
         "of net worth.",
         "P/B = Purchase price ÷ Book value"),
    Term("Premium", "—",
         "How much above standalone value you pay, as a percentage. You pay it "
         "because control is not for sale at market price.",
         "Premium = (Offer ÷ Standalone value) − 1"),
    Term("TCE", "Tangible Common Equity",
         "Equity with goodwill and intangibles stripped out — the 'hard' net "
         "worth.",
         "TCE = Equity − Goodwill − Intangibles"),
    Term("Synergies", "—",
         "Money the combined firm earns or saves that neither could alone. "
         "Cost synergies (removing duplicate overhead) are far more reliable "
         "than revenue synergies. In Switzerland both are harder: you cannot "
         "merge a French-language service desk into a German-language one."),
    Term("Run-rate", "—",
         "The full annual amount once something is completely in place, as "
         "opposed to what actually shows up in the first partial year."),
    Term("Phase-in", "—",
         "Synergies arrive gradually. '40 / 80 / 100' means 40% of the "
         "run-rate in year one, 80% in year two, all of it by year three."),
    Term("Accretion / Dilution", "—",
         "Whether a deal raises or lowers the buyer's earnings per share "
         "versus staying independent. Accretive is higher, dilutive is lower. "
         "It says nothing about risk, which is why it is never the whole "
         "answer."),
    Term("EPS", "Earnings Per Share",
         "Profit attributable to each share. Issuing new shares to fund a deal "
         "raises the denominator, so an equity-funded acquisition can dilute "
         "even a profitable target.",
         "EPS = Net income ÷ Shares outstanding"),
    Term("NPV", "Net Present Value",
         "Future cash flows discounted for how far away they are, minus what "
         "you paid. Positive means the deal creates value.",
         "NPV = Σ [ CFₙ ÷ (1 + r)ⁿ ] − Cost"),
    Term("IRR", "Internal Rate of Return",
         "The discount rate that makes NPV exactly zero — the deal's implied "
         "annual return.",
         "Find r such that NPV(r) = 0"),
    Term("Day-1 provision", "Purchase accounting adjustment",
         "At completion the acquired loan book's expected losses are "
         "re-estimated. If the buyer's estimate exceeds the reserve the target "
         "carried, the difference is booked immediately — a cost incurred "
         "before a single new loan is written."),
    Term("Condition precedent", "—",
         "Something that must happen before a deal can complete. Here: FINMA "
         "approval of the acquirer, and competition clearance where the "
         "thresholds are met.", swiss=True),
]

# --------------------------------------------------------------------------
CARDS = [
    Term("APR", "Annual Percentage Rate",
         "The yearly interest rate charged on a carried balance. In "
         "Switzerland this is capped by the VKKG, which is the single largest "
         "difference between this case and its North American equivalent."),
    Term("Transactor", "—",
         "Pays the balance in full every month. Generates interchange, pays no "
         "interest. Low risk, low capital — and barely profitable."),
    Term("Revolver", "—",
         "Carries a balance and pays interest on it. Where card profit comes "
         "from, and where the losses are."),
    Term("Revolve rate", "—",
         "The share of balances carried over rather than paid off. Swiss "
         "revolve rates are low — 24% to 62% here — because the culture and "
         "the affordability rules both discourage it."),
    Term("Utilisation", "—",
         "Balance divided by credit limit. It is both a risk signal to the "
         "lender and an input to the borrower's own credit standing.",
         "Utilisation = Balance ÷ Credit limit"),
    Term("Headroom", "Undrawn balance, available credit",
         "Credit granted but not yet borrowed. Invisible on the income "
         "statement, very much present in the risk calculation.",
         "Headroom = Credit limit − Balance"),
    Term("CLI", "Credit Limit Increase",
         "Raising a cardholder's maximum. In most markets it costs the lender "
         "nothing until drawn — which is what makes it both a cheap growth "
         "lever and a hazard. In Switzerland it triggers a fresh affordability "
         "assessment on the assumption the whole limit is drawn."),
    Term("Monoline", "—",
         "A lender doing essentially one product rather than full-service "
         "banking. Efficient and focused, with no deposit franchise to fall "
         "back on when that product turns."),
    Term("Securitisation", "—",
         "Bundling receivables and selling them to investors as securities, "
         "funding the book without deposits."),
    Term("Privatkunden / Firmenkunden", "Retail clients / corporate clients",
         "The standard Swiss split between individuals and companies. Retail "
         "books answer mainly to employment and interest rates; corporate "
         "books answer to output and, in Switzerland, to the franc.",
         swiss=True),
]

# --------------------------------------------------------------------------
REGIONS = [
    Term("Romandie", "French-speaking western Switzerland",
         "Geneva, Vaud, Neuchâtel, Jura and parts of Valais and Fribourg. "
         "Geneva finance and commodity trading plus the watch industry along "
         "the Jura arc, so the region is export- and franc-sensitive, and "
         "carries structurally higher unemployment than the Mittelland.",
         swiss=True),
    Term("Mittelland", "The central plateau",
         "The economic core running roughly Zurich–Bern–Basel, holding most of "
         "the population, most of the GDP and the highest property values. The "
         "most interest-rate and property-price sensitive region in the model.",
         swiss=True),
    Term("Alpen", "The alpine cantons",
         "Graubünden, Uri, Obwalden and the mountain regions. Tourism and "
         "construction dominate, employment is seasonal, and a strong franc "
         "empties the hotels — so this region carries the model's second "
         "highest franc sensitivity.", swiss=True),
    Term("Tessin", "Ticino — Italian-speaking southern Switzerland",
         "Lugano, Bellinzona and the south. Heavily dependent on cross-border "
         "workers and on the Italian economy, with tourism on top. The most "
         "employment-sensitive region here, and where Banca Alpina holds 64% "
         "of its book.", swiss=True),
]

# --------------------------------------------------------------------------
METHOD = [
    Term("Anchor year", "—",
         "The one fixed year all other figures are built from. Here FY2025."),
    Term("Pro forma", "'As if'",
         "Financial statements showing what the combined company would look "
         "like had the deal already closed. Always a construction, never an "
         "observation."),
    Term("Ties out / balances", "—",
         "Internal consistency checks. A balance sheet balances when assets "
         "equal liabilities plus equity; a statement ties out when its parts "
         "sum to the stated total.",
         "Assets = Liabilities + Equity"),
    Term("Plug", "Balancing figure",
         "A residual solved so a computed total matches a known one. Here it "
         "is the non-loan RWA — securities, operational risk, other assets — "
         "solved once so the base case reconciles exactly to each bank's "
         "reported total."),
    Term("Calibration", "—",
         "Scaling a model's output so its base case reproduces an observed "
         "figure. Value adjustments are calibrated to each bank's carried "
         "allowance, and the scaling factor doubles as a reserve-adequacy "
         "signal."),
    Term("Stress index", "—",
         "A single scalar summarising how bad conditions are, combining all "
         "five macro inputs with regional amplifiers. It drives the "
         "behavioural responses — drawdown, impairment migration — that are "
         "not probability of default itself."),
    Term("Beta (transmission)", "Sensitivity coefficient",
         "How strongly one product's default rate responds to one macro "
         "input. Commercial lending has the largest franc beta because "
         "exporters and tourism operators are who a strong franc actually "
         "hurts."),
    Term("Amplifier (regional)", "—",
         "A multiplier on the betas that differs by region, so an identical "
         "national shock lands unevenly. It is what makes a franc shock hurt "
         "Ticino roughly 60% more than the Mittelland."),
    Term("Sensitivity analysis", "—",
         "Change one input, hold the rest, and see how far the answer moves. "
         "It shows which assumptions actually carry the conclusion."),
    Term("Stress test", "—",
         "Re-running the model under a deliberately adverse scenario. Not a "
         "forecast — a structural test. The question is not whether the "
         "recession happens but whether you would still be standing."),
    Term("Shadow calculation", "—",
         "Running a second, unused accounting basis alongside the reported one "
         "purely for comparison. Here, IFRS 9 alongside Swiss GAAP, so the "
         "difference between the two regimes is visible rather than asserted."),
]


SECTIONS = [
    ("Swiss law and regulators", SWISS_LAW),
    ("Swiss accounting", SWISS_ACCOUNTING),
    ("Capital", CAPITAL),
    ("Credit risk", CREDIT_RISK),
    ("Earnings", EARNINGS),
    ("Deal and valuation", DEAL),
    ("The card business", CARDS),
    ("The four regions", REGIONS),
    ("Model and method", METHOD),
]

ALL_TERMS = [t for _, terms in SECTIONS for t in terms]


def search(query: str) -> list[tuple[str, list[Term]]]:
    """Filter every section by a free-text query across all fields."""
    q = query.strip().lower()
    if not q:
        return SECTIONS
    out = []
    for heading, terms in SECTIONS:
        hits = [
            t for t in terms
            if q in t.term.lower()
            or q in t.expansion.lower()
            or q in t.meaning.lower()
            or q in t.formula.lower()
        ]
        if hits:
            out.append((heading, hits))
    return out
