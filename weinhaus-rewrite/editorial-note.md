# Editorial note: Weinhaus rewrite (October 12, 2026)

## How this was checked

- **The source records could not be opened.** This environment's network policy blocked every evidence host: Justia, IARDC, CJR, judiciary.uk, supremecourt.gov, the Standard, YouTube, and the screenshot hosts (adamjohnflorek.com, edward-coach-weinhaus.com, edward-andrew-weinhaus.com). Quotations were checked against the current draft only. All 54 quotations in the rewrite appear verbatim in the draft, except "pink slime," which is from CJR's headline. A limited web search confirmed some items, noted below. Treat everything else as **checked against the draft but unverified against the record**.
- I read the Wilkinson Gacy profile from the full text pasted into the session.
- The rewrite runs about 2,100 words; the draft ran about 3,200.

## Substantive changes and corrections

1. **Subhead and site name.** I replaced "Understanding the Predator" with "The Coach's Record" in the visible subhead, `<title>`, OG and Twitter tags, and WebSite/WebPage/Article JSON-LD. The records show charges and pleadings. None of them is a finding that supports "predator," and with two criminal cases still open the word reads as a factual accusation. Reverting it means changing seven strings, but I recommend keeping the change.
2. **Deck.** "Illinois Disbarment Proceedings" is now "Respondent in an Illinois disciplinary case." An ARDC complaint does not by itself seek disbarment. "Cheerleading for a White Supremacist" and "Federal Sanctions" are replaced with record-based items.
3. **Current-status claims removed.** The draft said "The case is pending" (ARDC), "has appealed," "He is Judiciocracy's chief executive," and "He is its executive director." None had a current source. The rewrite uses dated phrasing instead: "court papers filed in 2025 identify him as its chief executive," "later appealed," and "a record printed on September 18 listed the warrant as active." It also adds that a charge is an accusation and that an ARDC hearing panel decides whether a complaint is proved.
4. **ARDC federal suit.** Judge Perry dismissed it in December 2025 with leave to amend. The 2026 appeal number (26-2265) suggests a later final order. The rewrite says only "later appealed." Check the docket.
5. **2019 Seventh Circuit.** Search results (Justia/CourtListener, *Weinhaus v. Cohen*, No. 18-3185) indicate the court found the appeal frivolous and granted the opponents' Rule 38 sanctions motion on July 16, 2019. A September 23, 2019 order sent the orders to the State Bar of California. I updated the draft's "met the standard for sanctions" to match. The draft said nothing about fees, and neither does the rewrite.
6. **Cut: "The notice carried no court order."** Litigation-hold letters never carry one, so the sentence implied an impropriety that doesn't exist.
7. **Cut: the unsourced school quote** ("accountability at schools is something for parents to take into their own hands"). The package names no newspaper or date for it. Restore it only with a citation.
8. **Homecoming sourcing.** The rewrite says the account of the evening is Weinhaus's own complaint, accepted as true on the motions to dismiss. Search confirms the defendants moved under Rule 12(b)(6). Confirm the opinion's facts section reads that way.
9. **No link drawn between Judiciocracy/ALABnews and Metric Media.** CJR's February 2026 description of him as a Metric lawyer is stated as of that date only.
10. **Added from docket searches:** the judges' names (April M. Perry; Jorge L. Alonso) and the due-process and equal-protection basis of the Scannicchio suit (7th Cir. No. 24-2473, nonprecedential order of June 18, 2025).
11. **Robinson material compressed.** I cut the Byline Times quotations and the Cleveland PCC/Redcar episode to keep the focus on Weinhaus, and removed both from the citations. The libel judgment, committal, purge and release remain. Search corroborated the 18-month term, the 10 admitted breaches, the 4-month remission, the "absence of contrition or remorse," and the May 27, 2025 release from HMP Woodhill.

## Claims whose sources I could not check

- **InMail:** subject line, wording, InMail status, and the "awaiting response" reminder. Also confirm that the message linked the November 27, 2023 piece, not another ALABnews item about the graduate.
- **LinkedIn profile wording** ("(Dr.) Edward 'Coach' Weinhaus, Esq." and the full headline). **No source for it is in the citation list.** Add a capture or cut it.
- **CJR (February 2026):** the wording of the quotations, "nearly twelve hundred," "LocalLabs," and "predecessors."
- **November 27, 2023 piece:** the byline and cartoon. "Use the strongest accurate description the record supports" needs the screenshot. The rewrite says only "its piece about the law graduate."
- **June 4 correspondence:** the recipient. The filenames say "ardc." Also confirm whether the "tracking," "juicy stories," and prison lines come from one message or several.
- **June 5 notice:** the recipient, and whether it sought *preservation* or *disclosure* of source identities. The rewrite keeps the draft's ambiguous phrasing.
- **ARDC complaint:** the filing month (the draft says April 2025; the rewrite says 2025) and every quotation from the complaint and the answer, including "litigiousness."
- **Supreme Court No. 25-725:** the February 2026 cert denial.
- **School case:** the $6 ticket, the three officers, "following her," "truly minimal," "with prejudice," and the June 2026 date. **Possible omission:** a Lake County Gazette report says Judge Alonso entered interim relief for Weinhaus on December 4, 2025. If that is accurate, fairness calls for a sentence about it.
- **Robinson LinkedIn message:** the date and recipient.
- **Maryland records:** the dates, charges, probable-cause markings, warrant, and the September 18 printout.

## Before publishing

- **Hero image.** It looks as though it may be AI-generated. Confirm it is a real photograph of Weinhaus. If it is not, the caption, alt text, and ImageObject caption must say "Illustration." I left the source, size, and alt text unchanged, as the brief requires.
- **Graduate anonymity.** Body, headings, captions, alt text, and JSON-LD reveal nothing beyond what the draft did. Two points to check:
  - The Maryland PDF's filename ("…for-Harassing-Law-School-Graduate.pdf") tells readers the complainant is the graduate, which the text does not. Rename it if that link shouldn't be made.
  - Confirm that both Maryland PDFs and all screenshots redact the graduate's name.
- **Disclosure.** If the site's publisher is a party to any proceeding described, a one-line disclosure would strengthen the piece.
- **Deployment.** `dateModified` is 2026-10-12, so change it to the actual install date if that differs. No analytics token is in the file; the serving layer should keep injecting it. Section IDs are preserved and the nav is reordered to match. Two IDs, `#bigotry` and `#someone-else-decides`, now carry the headings "Oyyyyy Tommy Tommy" and "Homecoming," which keeps old anchors working.
