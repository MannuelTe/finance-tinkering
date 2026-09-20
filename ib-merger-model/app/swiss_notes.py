"""Plain-English commentary on the Swiss adjustments, rendered in the app.

Written for a reader who knows banking but not Swiss law. Each note says what
the rule is, why it exists, and what it changed in this model.

This is a simplified teaching summary, not a statement of Swiss law, and
thresholds and rates move over time. Anyone doing this for real should take
advice from Swiss counsel and check the current FINMA circulars.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Note:
    title: str
    source: str      # the instrument the rule lives in
    body: str        # plain English
    effect: str      # what it changed in the model


ACCOUNTING = [
    Note(
        title="There is no IFRS 9 here, and that changes the shape of a downturn",
        source="FINMA Accounting Ordinance (RelV-FINMA); FINMA Circular 2020/1 "
               "\"Accounting – banks\"",
        body=(
            "Swiss banks do not report loan losses the way IFRS 9 banks do. IFRS 9 "
            "sorts every loan into three stages and forces a jump to *lifetime* "
            "expected loss the moment credit risk rises materially — before anyone "
            "has missed a payment. Swiss GAAP has no such staircase. It books an "
            "individual value adjustment when a specific exposure actually goes bad "
            "(*Einzelwertberichtigung*), and holds a broader provision for inherent "
            "default risks across the performing book.\n\n"
            "The practical difference is timing. IFRS 9 front-loads: provisions spike "
            "early, on a forecast. Swiss GAAP recognises losses closer to when they "
            "occur. Neither is more prudent in the abstract — but they behave very "
            "differently going into a recession."
        ),
        effect=(
            "The stage 1 → 2 cliff is gone. The engine computes Swiss GAAP value "
            "adjustments as the headline number, and runs an IFRS 9 shadow "
            "calculation alongside it so you can see the gap. Under stress the Swiss "
            "figure rises later and less sharply — which flatters the P&L on the way "
            "in and leaves a thinner reserve when losses actually land."
        ),
    ),
    Note(
        title="Reserves for general banking risks are a shock absorber with no IFRS twin",
        source="Art. 959a CO; RelV-FINMA",
        body=(
            "Swiss banks may build an explicit equity reserve for general banking "
            "risks (*Reserven für allgemeine Bankrisiken*). It is funded out of "
            "profits in good years, counts as CET1 capital, and can be released to "
            "the income statement when conditions turn. There is no equivalent line "
            "on an IFRS balance sheet.\n\n"
            "It does not create capital — the money is already inside CET1 either "
            "way. What it does is smooth reported earnings, because a release offsets "
            "the provision charge in the year the losses arrive."
        ),
        effect=(
            "Each bank carries a reserve balance. Under stress the model releases it "
            "against the provision charge and reports earnings both before and after "
            "the release, so you can see how much of the resilience is real capital "
            "and how much is presentation."
        ),
    ),
    Note(
        title="The book value you are buying may understate the bank",
        source="Art. 960a CO; RelV-FINMA",
        body=(
            "Swiss statutory accounting permits deliberately conservative valuation, "
            "and Swiss banks have a long tradition of carrying undisclosed reserves "
            "(*stille Reserven*) — assets held below their realistic value. The "
            "disclosure regime has tightened considerably, but the principle survives "
            "in the statutory single-entity accounts.\n\n"
            "For an acquirer this cuts the opposite way to the usual worry. The "
            "standard fear in diligence is that the target is worth less than it "
            "claims. Here the target may be worth more than its balance sheet admits, "
            "and the seller knows it."
        ),
        effect=(
            "Flagged as a diligence item rather than modelled. Goodwill is computed "
            "off reported book value; any hidden reserves uncovered in diligence "
            "would reduce it, and are a negotiating point on price."
        ),
    ),
]


CAPITAL = [
    Note(
        title="Swiss capital requirements sit above the Basel minimums",
        source="Capital Adequacy Ordinance (ERV); FINMA Circular 2011/2",
        body=(
            "Switzerland applies what the market calls the \"Swiss finish\": capital "
            "requirements deliberately set above the international Basel floor. FINMA "
            "sorts banks into five supervisory categories by size and risk, and the "
            "buffer requirement rises with the category. Banks therefore run CET1 "
            "ratios that look generous next to North American peers — that is the "
            "regime working as intended, not excess capital waiting to be released."
        ),
        effect=(
            "All three banks carry markedly higher CET1 ratios than the Canadian "
            "version of this case, and the management target is 12.0% rather than "
            "11.0%. The acquirer is a category 3 bank; both targets are category 4."
        ),
    ),
    Note(
        title="Mortgages carry their own extra capital charge",
        source="Art. 44 ERV — sectoral countercyclical capital buffer",
        body=(
            "Switzerland has a countercyclical buffer aimed specifically at "
            "residential mortgages, rather than at the balance sheet as a whole. It "
            "was reactivated in 2022 after concern about property valuations, and "
            "adds a capital charge on Swiss residential mortgage positions on top of "
            "the ordinary requirement.\n\n"
            "This matters enormously here, because Swiss retail banks are mortgage "
            "lenders first. A bank with a large mortgage book faces a materially "
            "higher capital requirement than its headline RWA suggests."
        ),
        effect=(
            "The model tracks mortgage RWA separately and adds a sectoral buffer on "
            "top of the base requirement. It is the reason the two deals differ in "
            "capital cost by more than their RWA alone would imply — Banca Alpina "
            "brings a mortgage book, and the buffer travels with it."
        ),
    ),
    Note(
        title="Raising the equity to pay for a deal is itself taxed",
        source="Federal Stamp Duty Act — issuance duty (Emissionsabgabe)",
        body=(
            "Switzerland levies a 1% federal issuance duty on newly created equity, "
            "above a modest exemption. Its abolition was put to a national vote in "
            "2022 and rejected, so it still applies.\n\n"
            "It is a small percentage on a large number. An acquirer that has to "
            "issue shares to restore its capital ratio pays for the privilege, and "
            "the cost scales with exactly the deals that strain capital most."
        ),
        effect=(
            "Any equity raise in the deal tab carries a 1% issuance duty, shown as a "
            "separate line. It makes the capital-hungry deal slightly worse again."
        ),
    ),
    Note(
        title="Swiss bond funding drags a 35% withholding tax behind it",
        source="Federal Withholding Tax Act (Verrechnungssteuer)",
        body=(
            "Interest on bonds issued by Swiss issuers attracts 35% withholding tax. "
            "Foreign investors can often reclaim it under a treaty, but the friction "
            "is real, and reform was rejected at referendum in 2022. It is a standing "
            "reason Swiss groups have historically issued debt through foreign "
            "vehicles."
        ),
        effect=(
            "Treated as a structuring note rather than modelled. Acquisition debt is "
            "priced at Swiss franc rates, which are low by international standards — "
            "the cheap end of the funding cost is genuine, the plumbing is not free."
        ),
    ),
]


CONSUMER = [
    Note(
        title="Consumer credit rates are capped by law, which is the single biggest change",
        source="Consumer Credit Act (KKG) Art. 14; Ordinance to the KKG (VKKG)",
        body=(
            "The Federal Council sets a maximum interest rate for consumer credit. It "
            "sits in the region of 12% for cash credit, with a slightly higher ceiling "
            "for card overdrafts, and it moves with reference rates.\n\n"
            "This dismantles the economic thesis that drives card lending in "
            "unregulated markets. There, the case for buying a card book is a spread "
            "of roughly 21% lending against 3% funding — around eighteen points of "
            "gross margin, wide enough to absorb heavy losses and still pay. In "
            "Switzerland the lending rate is capped near 12% and there is no legal "
            "route above it. The spread is roughly a third narrower, so the same book "
            "cannot carry the same loss rate."
        ),
        effect=(
            "Card APRs are set at 10.9% to 12.9% instead of 20% to 23%. Every card "
            "book in the case is less profitable and, necessarily, underwritten more "
            "tightly — which is why the Swiss probabilities of default are a fraction "
            "of the Canadian ones."
        ),
    ),
    Note(
        title="A credit limit increase requires a fresh affordability test — assuming the whole limit is drawn",
        source="KKG Art. 28 ff.; sanction under KKG Art. 32",
        body=(
            "Before granting or raising consumer credit, a Swiss lender must run a "
            "formal affordability assessment (*Kreditfähigkeitsprüfung*). Two features "
            "make it bite far harder than a generic suitability check.\n\n"
            "First, affordability is tested on the assumption that the credit is "
            "repaid within 36 months, even where the actual product has no such term. "
            "Second — and this is the decisive point for card lending — the assessment "
            "for an overdraft facility assumes the customer draws the **entire** "
            "limit. The lender cannot treat unused headroom as costless.\n\n"
            "The sanction is severe. A lender that breaches the assessment "
            "requirements in a material way forfeits not only the interest but the "
            "credit amount itself."
        ),
        effect=(
            "This is the legal answer to the exposure-migration problem the case is "
            "built around. In an unregulated market the lender grants headroom "
            "cheaply, and discovers only later that borrowers draw it down as they "
            "deteriorate. Swiss law forces that full-limit assumption up front, at "
            "grant. The management lever for limit increases is therefore constrained, "
            "and the model applies a smaller drawdown response than the Canadian "
            "version — the risk has partly been regulated out at origination."
        ),
    ),
    Note(
        title="Every consumer credit and card limit goes on a central register",
        source="KKG Art. 25 ff. — IKO register; ZEK credit bureau",
        body=(
            "Swiss lenders must report consumer credits and card limits to the IKO "
            "register, and the banks share credit information through ZEK. A lender "
            "assessing an application can therefore see the applicant's other "
            "commitments across the market, not merely its own.\n\n"
            "This closes the gap that makes bust-out fraud viable elsewhere, where a "
            "borrower can build clean histories across several issuers in parallel "
            "and draw them all at once."
        ),
        effect=(
            "Card loss rates across all three banks are set well below North American "
            "levels, and the stress response of the card books is correspondingly "
            "milder. Swiss card lending is a lower-margin, lower-loss business at both "
            "ends."
        ),
    ),
    Note(
        title="Mortgage lending is conservative by rule, not by choice",
        source="Self-regulation guidelines recognised as a minimum standard by FINMA",
        body=(
            "Swiss mortgage lending runs under binding self-regulation: a minimum "
            "down payment, a hard limit on how much of it may come from pension "
            "assets, and mandatory amortisation down to two thirds of the lending "
            "value within a set period. Lending is full recourse — the borrower stays "
            "liable after enforcement — and enforcement itself (*Betreibung*) is "
            "creditor-friendly.\n\n"
            "The result is that Swiss mortgage losses are close to negligible even "
            "through property downturns. The risk shows up as a capital charge and a "
            "valuation concern, not as a credit loss."
        ),
        effect=(
            "Mortgage LGD is set at 11–12%, against 14–15% in the Canadian version, "
            "and mortgage PDs are a fraction of the consumer figures. A property "
            "correction in this model hits capital through the sectoral buffer and "
            "collateral values, not through a wave of defaults."
        ),
    ),
]


TRANSACTION = [
    Note(
        title="FINMA has to approve the buyer before the deal can complete",
        source="Banking Act (BankG) Art. 3(2)(c) ff.",
        body=(
            "Anyone acquiring a qualified participation in a Swiss bank needs FINMA "
            "clearance, and the regulator assesses the acquirer's fitness, the "
            "governance of the combined group, and whether the resulting entity is "
            "adequately capitalised. The merger itself is governed by the Merger Act "
            "(*Fusionsgesetz*), which sets the corporate mechanics.\n\n"
            "The practical consequence is sequencing. An acquirer that would land "
            "below its capital target on completion cannot simply promise to fix it "
            "afterwards — the capital plan is part of what is approved."
        ),
        effect=(
            "The deal tab reports the capital position before any raise as well as "
            "after it, because the pre-raise figure is what a regulator looks at when "
            "assessing whether the transaction is fundable as structured."
        ),
    ),
    Note(
        title="Merger control counts bank size differently",
        source="Cartel Act (KG) Art. 9",
        body=(
            "Swiss merger control applies turnover thresholds, but for banks the "
            "Cartel Act substitutes a different measure of size rather than using "
            "ordinary turnover. Deals over the thresholds must be notified to the "
            "Competition Commission (COMCO/WEKO) before completion.\n\n"
            "There is also a specifically Swiss wrinkle: where FINMA judges a "
            "transaction necessary to protect creditors, the prudential interest can "
            "displace the competition analysis."
        ),
        effect=(
            "Not modelled. Flagged as a condition precedent with a timetable "
            "implication — a filing takes months, and the capital plan has to survive "
            "that window."
        ),
    ),
    Note(
        title="Where the combined bank is domiciled changes the tax rate materially",
        source="Cantonal and communal corporate income tax",
        body=(
            "Corporate tax in Switzerland is levied federally, cantonally and "
            "communally, so the effective rate depends on where the entity sits. The "
            "spread between the cheapest and most expensive cantons is large — "
            "roughly twelve percent against something closer to twenty.\n\n"
            "For a bank with a fixed domestic customer base the freedom is limited, "
            "but for a merged group deciding where the surviving entity should sit, "
            "several points of tax is not a rounding error."
        ),
        effect=(
            "The model uses a Zurich-based effective rate of 19.7%. A lower-tax "
            "domicile would lift every after-tax synergy figure in the deal tab by "
            "roughly a tenth."
        ),
    ),
    Note(
        title="Deposit protection is capped at the system level, not just per depositor",
        source="BankG Art. 37h ff.; esisuisse",
        body=(
            "Swiss deposit insurance protects CHF 100,000 per depositor per bank, but "
            "the scheme also has a ceiling on what it can pay out in aggregate, and "
            "it is funded by the surviving banks rather than pre-funded.\n\n"
            "A bank with a large, granular retail deposit base is therefore valuable "
            "in a way the balance sheet does not show: it is stable funding that does "
            "not run at the first sign of trouble."
        ),
        effect=(
            "Reflected in funding costs. The deposit-rich banks fund at 60–75 basis "
            "points; the wholesale-funded card specialist pays 185."
        ),
    ),
    Note(
        title="Three language regions is an operating cost, not just a map",
        source="Practice",
        body=(
            "A bank operating across the Romandie, the Mittelland and Ticino runs "
            "everything three times: documentation, contact centres, compliance "
            "review, marketing, and the consumer credit disclosures the KKG requires. "
            "Cost synergies in a Swiss retail merger are correspondingly harder to "
            "extract than headcount overlap suggests, because you cannot consolidate "
            "a French-language service desk into a German-language one."
        ),
        effect=(
            "Cost synergy assumptions are set below what a single-language market "
            "would support, and the integration cost per franc of acquired assets is "
            "higher."
        ),
    ),
]


SECTIONS = [
    ("Accounting — Swiss GAAP instead of IFRS", ACCOUNTING),
    ("Capital and tax", CAPITAL),
    ("Consumer credit law", CONSUMER),
    ("Doing the transaction", TRANSACTION),
]


HEADLINE = (
    "Moving this case to Switzerland is not a relabelling exercise. Three rules "
    "change the economics rather than the presentation: consumer credit rates are "
    "capped by statute, so the card spread that justifies the whole strategy is a "
    "third narrower; Swiss GAAP has no IFRS 9 staging, so provisions arrive later "
    "and more gently; and mortgages carry their own capital buffer, so a "
    "mortgage-heavy target costs more capital than its risk-weighted assets imply."
)
