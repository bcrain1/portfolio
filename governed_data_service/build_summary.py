"""Build the two-page portfolio brief only from verified release evidence."""
from pathlib import Path
import json
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

ROOT = Path(__file__).resolve().parent
NAVY = '#132B3B'
TEAL = '#087F8C'
INK = '#263E4D'
MUTED = '#506777'
PALE = '#EAF4F5'
W, H = 612, 792


def build():
    evidence = json.loads((ROOT / 'output/release_evidence.json').read_text())
    if evidence['status'] != 'VERIFIED':
        raise RuntimeError('Verified evidence required')
    path = ROOT / 'output/Brandon_Crain_Governed_Data_Service.pdf'
    c = canvas.Canvas(str(path), pagesize=(W, H))
    c.setTitle('Governed Data Service | Brandon Crain')
    c.setAuthor('Brandon Crain')
    c.setSubject('Independent synthetic data engineering demonstration')

    def text(s, x, y, width=508, size=10, color=INK, bold=False):
        style = ParagraphStyle('body', fontName='Helvetica-Bold' if bold else 'Helvetica',
                               fontSize=size, leading=size * 1.4, textColor=HexColor(color))
        p = Paragraph(s, style)
        _, height = p.wrap(width, H)
        p.drawOn(c, x, y-height)
        return y-height

    def rule(y):
        c.setStrokeColor(HexColor('#D4E1E7')); c.line(52, y, 560, y)

    def head(page, title, subtitle):
        c.setFillColor(HexColor(NAVY)); c.rect(0, H-170, W, 170, fill=1, stroke=0)
        text('BRANDON CRAIN  /  SELECTED ENGINEERING WORK', 52, H-36, color='#B3DDE2', size=9, bold=True)
        text(title, 52, H-65, size=26, color='#FFFFFF', bold=True)
        text(subtitle, 52, H-108, size=11, color='#E0EDF2')
        c.setFillColor(HexColor(PALE)); c.rect(52, 584, 508, 25, fill=1, stroke=0)
        text('SYNTHETIC DATA  |  LOCAL DEMONSTRATION', 62, 602, size=8, bold=True, color=TEAL)
        rule(51)
        text('Independent demonstration. No employer code, data or production claims.',52,41,size=8,color=MUTED)
        text(str(page)+' / 2',526,41,width=36,size=8,color=MUTED)

    def section(label, body, y):
        y=text(label.upper(),52,y,size=10,color=TEAL,bold=True)-7
        return text(body,52,y,size=10)-14

    head(1,'Governed Data Service','Correct an inspection record without losing its history - or exposing a half-published dataset.')
    y=section('The problem','An analyst finds an incorrect value in a fictional equipment inspection. Editing a data file directly can erase evidence, overwrite a newer correction, or leave readers with an incomplete dataset. This project makes the correction a reviewed, versioned operation.',565)
    y=section('The working demonstration','Propose a create, update or soft delete; switch to a separate reviewer; approve or reject with a reason. Readers see the current dataset and can inspect immutable historical snapshots. The console also walks through an expand, backfill and contract schema change.',y)
    text('HOW A CORRECTION BECOMES PUBLISHED DATA',52,y,size=9,color=TEAL,bold=True)
    y-=20
    labels=[('PROPOSE','Schema + revision'),('REVIEW','Separate demo role'),('COMMIT','Journal + pointer'),('READ','Versioned Parquet')]
    for i,(a,b) in enumerate(labels):
        x=52+i*130
        c.setFillColor(HexColor(PALE));c.roundRect(x,y-56,118,56,6,fill=1,stroke=0)
        text(a,x+10,y-10,width=98,size=10,color=TEAL,bold=True)
        text(b,x+10,y-30,width=98,size=8,color=MUTED)
        if i<3:
            c.setStrokeColor(HexColor(TEAL));c.line(x+119,y-28,x+127,y-28)
    y-=79
    y=section('The engineering decision','SQLite is the authoritative journal. A writer builds and verifies new Parquet files before committing the snapshot pointer together with the record change and audit event. Readers resolve a committed pointer; publication never means overwriting the previous dataset.',y)
    section('What this makes inspectable','FastAPI validation; role-aware review; optimistic revisions; idempotent retries; auditable soft deletion; partition manifests and hashes; failure recovery; and old/new client compatibility during a schema transition.',y)
    c.showPage()
    head(2,'Evidence and tradeoffs','Failure behavior is part of the demonstration, not an assumption hidden behind the happy path.')
    y=section('Verified release',f"{evidence['tests_passed']} automated tests passed. The review workflow was exercised in a browser. See docs/VALIDATION.md and output/release_evidence.json for test scope, environment and visual-review evidence.",565)
    checks=[('Retries','Same request replays its receipt; changed content under the same key conflicts.'),
            ('Competing edits','Approval rechecks the record revision inside the write transaction.'),
            ('Interrupted publish','Injected failures leave the prior committed snapshot readable.'),
            ('History and integrity','Old versions remain readable; corrupt snapshot content is rejected.'),
            ('Schema evolution','Expand, backfill and contract preserve values and enforce client compatibility.')]
    for label,body in checks:
        text(label,52,y,width=113,size=9,bold=True)
        end=text(body,177,y,width=383,size=9)
        y=min(y-32,end-10)
    y-=8
    y=section('Limits worth discussing','Switchable identities are a local simulation, not authentication. Snapshot creation holds SQLite\'s single-writer transaction. Failed writes may leave unreferenced files; the journal is not tamper-proof. Durability depends on the local operating system and filesystem. Cloud storage, distributed commits, production IAM and disaster recovery are outside this release.',y)
    y=section('Ten-minute interview walkthrough','Correct and review a value. Replay a request and provoke a stale edit. Compare historical snapshots. Walk old and new clients through migration. Then explain what would change for a multi-user production deployment. The included walkthrough supplies prompts and answers.',y)
    section('Provenance and use','All data and rules are invented. This independent build demonstrates engineering techniques, not an employer system or historical professional experience. Review and understand the walkthrough before presenting it.',y)
    c.save()
    print(path)


if __name__ == '__main__':
    build()

