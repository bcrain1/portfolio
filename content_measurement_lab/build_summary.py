"""Optional two-page work-samples PDF from the generated, reviewed results."""
from pathlib import Path
import json
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Flowable

ROOT=Path(__file__).resolve().parent
INK=colors.HexColor('#162a3a');TEAL=colors.HexColor('#087f8c');MUTED=colors.HexColor('#526879');PALE=colors.HexColor('#eaf3f5');LINE=colors.HexColor('#dbe5ea')
STYLES={
 'eyebrow':ParagraphStyle('eyebrow',fontName='Helvetica-Bold',fontSize=9,textColor=TEAL,leading=12,spaceAfter=7),
 'title':ParagraphStyle('title',fontName='Helvetica-Bold',fontSize=27,textColor=INK,leading=31,spaceAfter=8),
 'subtitle':ParagraphStyle('subtitle',fontName='Helvetica',fontSize=11,textColor=MUTED,leading=15,spaceAfter=15),
 'h':ParagraphStyle('h',fontName='Helvetica-Bold',fontSize=15,textColor=INK,leading=19,spaceAfter=8,spaceBefore=11),
 'body':ParagraphStyle('body',fontName='Helvetica',fontSize=10.5,textColor=INK,leading=15,spaceAfter=8),
 'small':ParagraphStyle('small',fontName='Helvetica',fontSize=9,textColor=MUTED,leading=12.5,spaceAfter=7),
 'label':ParagraphStyle('label',fontName='Helvetica-Bold',fontSize=10,textColor=TEAL,leading=14,spaceAfter=6),
}
def p(text,style='body'):return Paragraph(text,STYLES[style])

class GapChart(Flowable):
    def __init__(self,raw,adjusted):super().__init__();self.width=504;self.height=101;self.raw=raw;self.adjusted=adjusted
    def draw(self):
        c=self.canv;c.setFillColor(PALE);c.roundRect(0,0,504,101,7,fill=1,stroke=0)
        c.setFont('Helvetica-Bold',10);c.setFillColor(INK);c.drawString(14,83,'The apparent advantage shrinks after accounting for audience mix')
        for label,value,y in [('Raw return difference',self.raw,53),('Standardized difference',self.adjusted,22)]:
            c.setFont('Helvetica',9.5);c.setFillColor(INK);c.drawString(14,y,label)
            c.setFillColor(TEAL);c.roundRect(176,y-3,max(2,value*6),12,3,fill=1,stroke=0)
            c.setFillColor(INK);c.setFont('Helvetica-Bold',10);c.drawString(405,y,f'{value:+.1f} pp')

def footer(c,doc):
    c.setStrokeColor(LINE);c.line(54,43,558,43)
    c.setFont('Helvetica',8);c.setFillColor(MUTED)
    c.drawString(54,29,'BRANDON CRAIN  |  Independent synthetic work samples  |  September 2026')
    c.drawRightString(558,29,f'{doc.page} / 2')

def build():
    r=json.loads((ROOT/'output/results.json').read_text())
    output=ROOT/'output/Brandon_Crain_Selected_Work_Samples.pdf'
    doc=SimpleDocTemplate(str(output),pagesize=(612,792),rightMargin=54,leftMargin=54,topMargin=40,bottomMargin=57,
      title='Brandon Crain - Selected Analytics and Data Systems Work Samples',author='Brandon Crain',subject='Independent synthetic portfolio demonstrations')
    a,b=r['groups']['1'],r['groups']['0'];raw=100*(a['rate']-b['rate']);adj=100*r['standardized_gap']
    story=[p('BRANDON CRAIN  /  ANALYTICS & DATA SYSTEMS','eyebrow'),p('Selected work samples','title'),
      p('Metric design. Trustworthy data. Decisions that survive scrutiny.<br/>Austin, TX | bmcrain1@gmail.com | linkedin.com/in/brandon-crain','subtitle'),
      p('01  NEW CONTENT EXPERIENCE MEASUREMENT LAB','eyebrow'),
      p('Does higher observed return justify expanding a new live experience?','h'),
      p('This independent Python/SQL demonstration follows a product question from synthetic telemetry to a decision memo. It connects explicit eligibility rules, event quality, member-level metrics, a filterable dashboard, and an explanation of selection bias.'),
      p('<b>What is implemented.</b> Seeded event generation; duplicate and conflicting-ID handling; event-time sessionization; first-day adoption and engagement; seven-day return; Wilson intervals; and descriptive standardization by pre-index activity.'),
      GapChart(raw,adj),Spacer(1,9),
      p(f'<b>Observed in the simulation:</b> {r["mature_n"]:,} of {r["members"]:,} members have seven-day event-time maturity. Return is {a["rate"]:.1%} among exposed members ({a["returned"]}/{a["n"]}) and {b["rate"]:.1%} among unexposed members ({b["returned"]}/{b["n"]}). Another {r["excluded_immature"]} members are excluded from all displayed member rates.'),
      p('<b>Interpretation.</b> Frequent viewers are deliberately more likely to be exposed and to return. The simulator gives exposure no causal effect. Standardization removes much of the raw difference; the remaining gap is not evidence of incremental benefit.'),
      p('<b>Decision.</b> Validate instrumentation, monitor playback-quality guardrails, then design a randomized exposure study. Observed return alone does not establish satisfaction or product value.'),
      p('TECHNICAL EVIDENCE','label'),
      p('Inspectable SQL, hand-calculated and failure-mode tests, reproducible CSV/SQLite outputs, and an offline HTML dashboard. Core execution uses the Python standard library; PDF export uses ReportLab.','small'),
      p('Scope: synthetic data only; no Netflix or employer data. No completed A/B test, causal lift, production deployment, or distributed-scale claim. AI-assisted implementation; source and review walkthrough accompany the project.','small'),
      PageBreak(),
      p('BRANDON CRAIN  /  SELECTED WORK SAMPLES','eyebrow'),p('Reliable inputs.<br/>Explainable systems.','title'),
      p('Two existing independent demonstrations complement the measurement lab. Their documentation was reviewed for this summary; their full test suites were not rerun for this packet.','subtitle'),
      p('02  DATA RECONCILIATION WORKBENCH','eyebrow'),
      p('Make migration exceptions visible before trusting the output.','h'),
      p('<b>Question.</b> How can inconsistent business records be reconciled without silently accepting ambiguous matches or duplicating records on a rerun?'),
      p('<b>Demonstrated workflow.</b> A local Python/Tkinter application validates a structured Excel import, normalizes customer, product and transaction data, and surfaces schema errors and possible duplicates. A human reviews ambiguous matches before accepted records are committed transactionally.'),
      p('<b>Evidence and relevance.</b> Dry-run results, Excel/CSV/HTML/JSON exports and audit records make the transformation reviewable. Identical reruns are recognized. The analytics connection is trustworthy source data with explicit exceptions and reconciliation.'),
      p('Boundary: fictional data and local execution. No paid-client deployment, verified business savings, security certification or production-scale claim.','small'),
      Spacer(1,10),
      p('03  RELIABLE EVENT-DRIVEN OPERATIONS BACKEND','eyebrow'),
      p('Keep retries and recovery from corrupting system state.','h'),
      p('<b>Question.</b> How can a system process repeated events and conflicting resource requests while preserving evidence of successful and failed operations?'),
      p('<b>Demonstrated workflow.</b> A FastAPI/SQLAlchemy/SQLite service with a Streamlit dashboard models transactional resource allocation, idempotent events, artifact custody, and SHA-256-verified backup. Operational views expose failures and recovery states.'),
      p('<b>Evidence and relevance.</b> Synthetic scenarios cover duplicate and out-of-order events, allocation conflicts, failed checksums and retry. Reliable event semantics and inspectable state are foundations for dependable analytical outputs.'),
      p('Boundary: single-host synthetic system. Application-enforced audit controls are not tamper-proof or WORM storage. Multi-instance concurrency and production access controls require additional work.','small'),
      Spacer(1,8),p('REVIEW & PROVENANCE','label'),
      p('These are independent, AI-assisted portfolio demonstrations, separate from employment achievements. The new lab includes source, reproducible outputs, tests and a metric-review walkthrough. Source and walkthrough: <link href="https://github.com/bcrain1/portfolio/tree/main/content_measurement_lab" color="#087f8c">github.com/bcrain1/portfolio/tree/main/content_measurement_lab</link>.','small')]
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    print(output)

if __name__=='__main__':build()
