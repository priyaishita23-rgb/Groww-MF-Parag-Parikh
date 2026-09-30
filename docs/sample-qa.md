# Sample Q&A

Generated from the running assistant on 2026-09-30 by `python scripts/make_samples.py`. Do not edit by hand.

Retrieval backend: **tfidf**. Answers are the stored corpus sentences, not generated. Either way the citation is taken from the retrieved chunk.

> Facts-only assistant. No investment advice. Figures are quoted from public AMC/SEBI/AMFI documents and can change - always confirm on the linked source.

### Fact - expense ratio

**Q. What is the expense ratio of Parag Parikh Flexi Cap Fund?**

Parag Parikh Flexi Cap Fund's base expense ratio is 1.05% for the Regular Plan and 0.53% for the Direct Plan, as on the last business day of August 2026. Base expense ratio is exclusive of GST on management fees and of other permitted add-ons; the AMC publishes the current applicable TER separately.

Last updated from sources: August 31, 2026  
Source: [PPFAS Monthly Factsheet - August 2026](https://amc.ppfas.com/downloads/factsheet/2026/ppfas-mf-factsheet-for-August-2026.pdf)

<sub>route: `fact` · chunk `C01` · score `0.7513`</sub>

### Fact - ELSS lock-in

**Q. What is the lock-in period for the ELSS Tax Saver Fund?**

Units of Parag Parikh ELSS Tax Saver Fund cannot be assigned, transferred, pledged, redeemed or switched out until completion of 3 years from the date of allotment of the respective units. The AMC may change the lock-in period prospectively only to the extent permitted under the Equity Linked Saving Scheme, 2005.

Last updated from sources: August 31, 2026  
Source: [KIM - Parag Parikh ELSS Tax Saver Fund](https://amc.ppfas.com/downloads/parag-parikh-tax-saver-fund/kim-parag-parikh-tax-saver-fund.pdf)

<sub>route: `fact` · chunk `C20` · score `0.676`</sub>

### Fact - exit load

**Q. What is the exit load on Parag Parikh Liquid Fund?**

Parag Parikh Liquid Fund has no entry load and a graded exit load within the first 7 calendar days: 0.0070% on Day 1, 0.0065% Day 2, 0.0060% Day 3, 0.0055% Day 4, 0.0050% Day 5, 0.0045% Day 6 and 0.0000% from Day 7 onwards. Any exit load charged, net of GST, is credited back to the Scheme.

Last updated from sources: August 31, 2026  
Source: [Parag Parikh Liquid Fund - scheme page](https://amc.ppfas.com/schemes/parag-parikh-liquid-fund/)

<sub>route: `fact` · chunk `C14` · score `0.5979`</sub>

### Fact - minimum SIP

**Q. What is the minimum SIP for the Conservative Hybrid Fund?**

The minimum SIP in Parag Parikh Conservative Hybrid Fund is Rs. 1,000 for a monthly SIP and Rs. 3,000 for a quarterly SIP.

Last updated from sources: August 31, 2026  
Source: [PPFAS Monthly Factsheet - August 2026](https://amc.ppfas.com/downloads/factsheet/2026/ppfas-mf-factsheet-for-August-2026.pdf)

<sub>route: `fact` · chunk `C42` · score `0.9992`</sub>

### Fact - riskometer

**Q. What does the riskometer say for Parag Parikh Dynamic Asset Allocation Fund?**

The scheme riskometer for Parag Parikh Dynamic Asset Allocation Fund reads Moderately High Risk, as on August 31, 2026. The riskometer is a SEBI-mandated risk label and is re-evaluated by the AMC every month.

Last updated from sources: August 31, 2026  
Source: [Parag Parikh Dynamic Asset Allocation Fund - scheme page](https://amc.ppfas.com/schemes/parag-parikh-dynamic-asset-allocation-fund/)

<sub>route: `fact` · chunk `C53` · score `0.7878`</sub>

### Fact - benchmark

**Q. Which benchmark does the ELSS Tax Saver Fund use?**

The benchmark of Parag Parikh ELSS Tax Saver Fund is NIFTY 500 (TRI), which is also its AMFI Tier I benchmark.

Last updated from sources: August 31, 2026  
Source: [PPFAS Monthly Factsheet - August 2026](https://amc.ppfas.com/downloads/factsheet/2026/ppfas-mf-factsheet-for-August-2026.pdf)

<sub>route: `fact` · chunk `C61` · score `0.6426`</sub>

### Fact - statements

**Q. How do I download my capital gains statement?**

PPFAS routes statement requests through its registrar CAMS: on the AMC's Investor Desk page, use the Capital Gain / Loss Statement link to generate the statement for your folio. The same page also offers the Account Statement and the Exit Load Statement.

Last updated from sources: September 2026  
Source: [PPFAS - Investor Desk (request statements)](https://amc.ppfas.com/investor-desk/)

<sub>route: `fact` · chunk `C100` · score `0.653`</sub>

### Ambiguous - asks which scheme

**Q. What is the exit load?**

That figure differs by scheme, so tell me which one you mean: Parag Parikh Flexi Cap Fund, Parag Parikh ELSS Tax Saver Fund, Parag Parikh Conservative Hybrid Fund, Parag Parikh Dynamic Asset Allocation Fund, Parag Parikh Liquid Fund.

Source: [PPFAS - Schemes](https://amc.ppfas.com/schemes/)

<sub>route: `clarify`</sub>

### Refusal - opinion

**Q. Should I buy Parag Parikh Flexi Cap Fund?**

I'm a facts-only assistant, so I can't say whether a scheme suits you or comment on your portfolio. I can quote published facts such as expense ratio, exit load, lock-in, minimum SIP, riskometer or benchmark.

Source: [AMFI - Risks in mutual funds](https://www.amfiindia.com/investor/knowledge-center-info?zoneName=riskInMutualFunds)

<sub>route: `refusal:advice`</sub>

### Refusal - performance

**Q. What were the 5-year returns of the flexi cap fund?**

I don't calculate or compare returns. Scheme performance is published in the AMC's official monthly factsheet, which is the right place to read it alongside the standard disclaimers.

Source: [PPFAS - Factsheet archive](https://amc.ppfas.com/downloads/factsheet/)

<sub>route: `refusal:performance`</sub>

### Refusal - PII

**Q. My PAN is ABCDE1234F, can you check my exit load?**

I can't take a PAN here, and nothing you typed has been stored. Please re-ask without any personal or account details - I only answer general scheme facts from public documents.

Source: [PPFAS - Schemes](https://amc.ppfas.com/schemes/)

<sub>route: `refusal:pii`</sub>

### Out of scope

**Q. What is the capital of France?**

I don't have that in my sources. I cover expense ratio, exit and entry load, lock-in, minimum investment and SIP, riskometer, benchmark, scheme category, inception date, fund managers and how to download statements, for five PPFAS schemes.

Source: [PPFAS - Schemes](https://amc.ppfas.com/schemes/)

<sub>route: `no_answer`</sub>
