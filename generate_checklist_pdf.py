#!/usr/bin/env python3
"""Generate the lead-magnet checklist PDF.

    python3 generate_checklist_pdf.py   ->  articles/materials-failure-cost-checklist.pdf

Kept separate from generate_pdfs*.py because those render the twelve sector
briefings and are a matched set; this is one standalone document with a
different layout (numbered questions with guidance, no article body) and a
different job — it is the gated download behind checklist.html.

Colours and page geometry are deliberately the same as generate_pdfs_v2.py so
the two sit together in a reader's downloads folder without looking unrelated.
"""

import os

from reportlab import rl_config
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                HRFlowable, KeepTogether, Table, TableStyle)

# Without this, reportlab stamps a creation timestamp and a random document ID
# into every build, so the committed PDF shows a diff on each regeneration even
# when nothing about it has changed.
rl_config.invariant = 1

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "articles", "materials-failure-cost-checklist.pdf")

PRIMARY = HexColor("#1a3a5c")
ACCENT = HexColor("#2d8cf0")
DARK = HexColor("#0f2740")
LIGHT_BG = HexColor("#f7f9fc")
BORDER = HexColor("#e2e8f0")
TEXT_COLOR = HexColor("#333333")
MUTED = HexColor("#666666")


# ------------------------------------------------------------------ content
#
# Four groups of three. The order is deliberate: cost first, because it is the
# only section that reliably gets an executive to keep reading; evidence second,
# because it is the only section that is time-critical; cause third; exposure
# last, because it is the question people avoid asking until it is expensive.

SECTIONS = [
    ("Part 1 — What is it actually costing?",
     "Almost every one of these problems is escalated on a number that turns "
     "out to be a fraction of the real one. Establish the real one first, "
     "because it sets how much investigation is proportionate.",
     [
         ("What is the fully loaded cost per month?",
          "Scrap and rework are the visible part. Add returns and warranty reserve, "
          "expedited freight, held or quarantined inventory, line downtime, the "
          "engineering and quality hours already spent, and any price concession "
          "made to keep a customer. Write down one monthly figure.",
          "If you cannot produce that figure in an afternoon, that is itself a "
          "finding: nobody currently owns the problem end to end."),
         ("What decision is waiting on the answer?",
          "Releasing a held batch. Approving or reversing a material substitution. "
          "Requalifying a supplier. Committing tooling. Settling or contesting a "
          "claim. Name the decision explicitly.",
          "\"Why did it fail\" has answers at many depths. The decision is what "
          "determines how deep the investigation has to go — and therefore what "
          "it should cost."),
         ("How long has this been open, and what has already been spent on it?",
          "Count the engineering hours, the trial runs, the sample shipments and "
          "the meetings. Compare that with the cost of a scoped external "
          "investigation.",
          "A problem that has consumed six months of internal attention without "
          "converging is usually not going to converge with more of the same."),
     ]),
    ("Part 2 — What evidence still exists?",
     "This is the time-critical section. Evidence is lost through ordinary, "
     "well-intentioned handling far more often than through neglect, and once "
     "it is gone no amount of budget recovers it.",
     [
         ("Have the failed parts been preserved exactly as found?",
          "Not cleaned, not cut, not re-dried, not re-processed, not returned to "
          "the supplier. Fracture surfaces in particular carry the signature of "
          "the failure mechanism and are destroyed by handling.",
          "If parts have already been altered, record what was done and by whom. "
          "That record is itself evidence, and concealing it is far worse than "
          "the alteration."),
         ("Do you have retains from the material lot in question?",
          "Unused material from the same lot, with its certificate of analysis, "
          "packaging and labels. Also retains from a lot that was working, if one "
          "exists — a comparison is worth more than an absolute measurement.",
          "Without a retain, a material-related cause can often be inferred but "
          "not demonstrated. With one, it can usually be settled."),
         ("Do you have the process data from the period in question?",
          "Machine settings, drying records, melt and mould temperatures, cycle "
          "times, residence time, regrind fraction, tool and cavity identity, "
          "shift and operator, and the maintenance log.",
          "Data that exists only in an operator's memory is not data. Extract and "
          "date-stamp it now rather than after someone leaves."),
     ]),
    ("Part 3 — What do you actually know about the cause?",
     "The aim here is to separate what has been demonstrated from what has been "
     "asserted confidently for long enough that it now sounds demonstrated.",
     [
         ("Is this one failure mode, or several?",
          "Sort the rejects by defect type rather than counting them. Then sort by "
          "machine, tool, cavity, shift and material lot.",
          "A single mechanism and three unrelated ones look identical on a scrap "
          "report and need completely different responses. This breakdown is "
          "frequently the whole diagnosis."),
         ("What changed before it started?",
          "Resin lot or grade, supplier, additive or masterbatch package, regrind "
          "practice, tooling or a tool repair, drying equipment, ambient humidity "
          "or season, an operator, a shift pattern, a cleaning agent, a downstream "
          "customer's use.",
          "The date the problem started is usually the single most informative "
          "fact available, and it is usually knowable to within a week."),
         ("Has any explanation been tested, or only argued?",
          "For each hypothesis on the table, write down what evidence supports it "
          "and what evidence would refute it.",
          "A hypothesis that nothing could refute is not a hypothesis. If every "
          "candidate explanation on your list is in that category, the "
          "investigation has not started yet."),
     ]),
    ("Part 4 — What is the exposure?",
     "The questions people leave until last, and the ones that most often "
     "determine whether the investigation should have been scoped differently "
     "from the beginning.",
     [
         ("Is anyone outside the company already asking about cause?",
          "A customer, an insurer, a regulator, a distributor, or counsel for any "
          "of them. Note who, when they first asked, and what has been said to "
          "them in writing.",
          "Informal written reassurance given early is one of the most common ways "
          "a manageable quality problem becomes an expensive legal one."),
         ("Could this become a product-liability, IP or supply dispute?",
          "Consider injury or property damage, a contract with a specification or "
          "conformance clause, a competitor's patent, or a supplier who has "
          "already denied responsibility.",
          "If the answer is anything other than a confident no, the investigation "
          "should be scoped for that possibility now. Work commissioned as a plant "
          "investigation and repurposed as evidence later is materially weaker."),
         ("If your current best explanation is wrong, what does that cost?",
          "Price the consequence of acting on the current theory and being "
          "mistaken: an ineffective corrective action, a recall that did not need "
          "to happen, a supplier wrongly blamed, or a claim conceded that could "
          "have been defended.",
          "This is the number that decides whether independent review is worth "
          "commissioning. If it is small, keep the problem in-house."),
     ]),
]

READING = [
    ("Mostly confident answers, exposure low",
     "Keep it in-house. You have the evidence, the history and the cost picture, "
     "and the consequence of being wrong is affordable. An outside view would "
     "add cost without adding much."),
    ("Confident on cost, thin on evidence",
     "Act on Part 2 today. Preserving parts, retains and process data costs "
     "almost nothing this week and cannot be done at all next month."),
    ("Several competing explanations, none tested",
     "This is the case where independent review usually pays for itself, because "
     "the value is in discriminating between hypotheses rather than in generating "
     "more of them."),
    ("Any yes in Part 4",
     "Scope the work for that possibility from the start, and take advice before "
     "putting further conclusions in writing."),
]


# ------------------------------------------------------------------- styles

def get_styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle('DocTitle', fontName='Helvetica-Bold', fontSize=23,
                         leading=28, textColor=PRIMARY, spaceAfter=8))
    s.add(ParagraphStyle('DocSub', fontName='Helvetica', fontSize=12.5,
                         leading=18, textColor=MUTED, spaceAfter=18))
    s.add(ParagraphStyle('Tag', fontName='Helvetica-Bold', fontSize=9.5,
                         leading=13, textColor=ACCENT, spaceAfter=10))
    s.add(ParagraphStyle('PartHead', fontName='Helvetica-Bold', fontSize=15,
                         leading=20, textColor=PRIMARY, spaceBefore=22,
                         spaceAfter=6))
    s.add(ParagraphStyle('PartIntro', fontName='Helvetica-Oblique', fontSize=10.5,
                         leading=16, textColor=MUTED, spaceAfter=14))
    s.add(ParagraphStyle('QHead', fontName='Helvetica-Bold', fontSize=12,
                         leading=17, textColor=DARK, spaceAfter=5))
    s.add(ParagraphStyle('QBody', fontName='Helvetica', fontSize=10.5,
                         leading=16, textColor=TEXT_COLOR, spaceAfter=7))
    s.add(ParagraphStyle('QWhy', fontName='Helvetica', fontSize=10,
                         leading=15, textColor=PRIMARY, leftIndent=10,
                         spaceAfter=2))
    s.add(ParagraphStyle('Body', fontName='Helvetica', fontSize=10.5,
                         leading=16, textColor=TEXT_COLOR, spaceAfter=9))
    s.add(ParagraphStyle('Contact', fontName='Helvetica', fontSize=10.5,
                         leading=16, textColor=PRIMARY, alignment=TA_CENTER,
                         spaceAfter=3))
    s.add(ParagraphStyle('Fine', fontName='Helvetica', fontSize=8, leading=11,
                         textColor=MUTED, alignment=TA_CENTER))
    return s


def question(story, st, n, head, body, why):
    """One numbered question, kept on a single page.

    KeepTogether matters here: a question split from its guidance across a page
    break reads as two unrelated fragments, and this document is meant to be
    worked through with a pen.
    """
    cell = [Paragraph("%d. %s" % (n, head), st['QHead']),
            Paragraph(body, st['QBody']),
            Paragraph("<b>Why it matters:</b> %s" % why, st['QWhy'])]
    table = Table([[cell]], colWidths=[6.3 * inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BG),
        ('BOX', (0, 0), (-1, -1), 0.75, BORDER),
        ('LINEBEFORE', (0, 0), (0, -1), 2.5, ACCENT),
        ('LEFTPADDING', (0, 0), (-1, -1), 14),
        ('RIGHTPADDING', (0, 0), (-1, -1), 14),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(KeepTogether([table, Spacer(1, 10)]))


def build():
    st = get_styles()
    story = []

    story.append(Paragraph("MATERIALS &amp; MANUFACTURING DECISIONS", st['Tag']))
    story.append(Paragraph(
        "The Executive&rsquo;s 12-Question Materials Failure "
        "&amp; Manufacturing Cost Checklist", st['DocTitle']))
    story.append(Paragraph(
        "A short guide for deciding whether a product failure, quality problem, "
        "material change or process issue requires independent technical review "
        "&mdash; or whether your own team should keep it.", st['DocSub']))
    story.append(HRFlowable(width="100%", thickness=2, color=ACCENT,
                            spaceAfter=16))

    story.append(Paragraph(
        "This is not a sales document. Several of the twelve questions are "
        "designed to establish that a problem does <i>not</i> need outside help, "
        "which is the right answer more often than it is the profitable one. "
        "Work through it with the people who actually see the parts.", st['Body']))
    story.append(Paragraph(
        "<b>One instruction before you start:</b> if failed parts still exist, "
        "stop anyone from cleaning, cutting, re-drying or shipping them back "
        "until you have finished Part 2. That single step preserves more "
        "investigative options than everything else in this document combined.",
        st['Body']))

    n = 0
    for title, intro, questions in SECTIONS:
        story.append(Paragraph(title, st['PartHead']))
        story.append(Paragraph(intro, st['PartIntro']))
        for head, body, why in questions:
            n += 1
            question(story, st, n, head, body, why)

    story.append(Paragraph("How to read your answers", st['PartHead']))
    story.append(Paragraph(
        "There is no score. What matters is the pattern:", st['PartIntro']))
    for label, advice in READING:
        story.append(Paragraph("<b>%s.</b> %s" % (label, advice), st['Body']))

    story.append(Paragraph("The next 48 hours", st['PartHead']))
    story.append(Paragraph(
        "Whatever else you decide: quarantine and photograph the failed parts as "
        "found, secure a retain from the material lot involved, export the "
        "process data for the period, and write down the date the problem "
        "started and what changed around it. None of that commits you to "
        "anything, and all of it becomes impossible later.", st['Body']))

    # ---- contact block
    story.append(Spacer(1, 18))
    story.append(HRFlowable(width="100%", thickness=1, color=BORDER,
                            spaceBefore=6, spaceAfter=16))
    story.append(Paragraph(
        "If the pattern points to independent review:", st['Contact']))
    story.append(Paragraph(
        "<b>Professor Joshua U. Otaigbe, PhD, CEng, FIMMM, CSci, FAEng, FSPE</b>",
        st['Contact']))
    story.append(Paragraph(
        "Founder &amp; Principal Partner, Flaney Associates, LLC", st['Contact']))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Manufacturers and product teams: info@flaneyassociates.com "
        "&nbsp;|&nbsp; +1 (601) 402-7282", st['Contact']))
    story.append(Paragraph(
        "Attorneys (confidential conflict check): jotaigbe@flaneyassociates.com "
        "&nbsp;|&nbsp; +1 (601) 451-8452", st['Contact']))
    story.append(Spacer(1, 14))
    story.append(HRFlowable(width="40%", thickness=1, color=ACCENT,
                            spaceBefore=2, spaceAfter=12))
    story.append(Paragraph(
        "Please do not send confidential samples, files or evidence before an "
        "engagement agreement is in place.", st['Fine']))
    story.append(Paragraph(
        "&copy; 2026 Flaney Associates, LLC. Provided for general information "
        "only; it is not legal advice and does not create an engagement.",
        st['Fine']))

    doc = SimpleDocTemplate(
        OUT, pagesize=letter,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.85 * inch, rightMargin=0.85 * inch,
        title="The Executive's 12-Question Materials Failure & Manufacturing "
              "Cost Checklist",
        author="Joshua U. Otaigbe")
    doc.build(story)
    print("  Created: %s (%d bytes)" % (OUT, os.path.getsize(OUT)))


if __name__ == "__main__":
    build()
