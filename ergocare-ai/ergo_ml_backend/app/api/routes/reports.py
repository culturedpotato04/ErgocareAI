"""
Reports route — v3
POST /{session_id}/complete  → score + build report, persist, return
GET  /{session_id}/report    → JSON report
GET  /{session_id}/report.pdf → PDF download with client name, audio list, full data
"""
import io
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.models.assessment import AssessmentSession
from app.models.schemas import CompleteSessionOut, RiskScores, ReportData
from app.domain.scoring import calculate_scores, build_report

router = APIRouter()


def _answers_as_dicts(session: AssessmentSession) -> list:
    return [
        {"question_id": a.question_id, "typed_answer": a.typed_answer, "transcript": a.transcript}
        for a in session.answers
    ]


# ── Complete session → score + report ────────────────────────────────────────

@router.post("/{session_id}/complete", response_model=CompleteSessionOut)
def complete_session(session_id: str, db: Session = Depends(get_db)):
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.answers:
        raise HTTPException(status_code=422, detail="No answers — cannot score empty session")

    answers = _answers_as_dicts(session)
    scores: RiskScores = calculate_scores(answers)
    report: ReportData = build_report(scores, answers)

    session.completed_at         = datetime.now(timezone.utc)
    session.overall_risk         = scores.overall_risk
    session.posture_risk         = scores.posture_risk
    session.eye_strain           = scores.eye_strain
    session.workload_stress      = scores.workload_stress
    session.musculoskeletal_risk = scores.musculoskeletal_risk
    session.recovery_risk        = scores.recovery_risk
    session.report_json          = report.model_dump()
    db.commit()

    return CompleteSessionOut(session_id=session_id, scores=scores, report=report)


# ── Get JSON report ───────────────────────────────────────────────────────────

@router.get("/{session_id}/report")
def get_report(session_id: str, db: Session = Depends(get_db)):
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.completed_at or not session.report_json:
        raise HTTPException(status_code=409, detail="Session not yet completed")
    return {
        "session_id":   session_id,
        "completed_at": session.completed_at,
        "client": {
            "name":  session.client_name,
            "email": session.client_email,
            "phone": session.client_phone,
            "age":   session.client_age,
            "job":   session.client_job,
        },
        "scores": {
            "overall_risk":         session.overall_risk,
            "posture_risk":         session.posture_risk,
            "eye_strain":           session.eye_strain,
            "workload_stress":      session.workload_stress,
            "musculoskeletal_risk": session.musculoskeletal_risk,
            "recovery_risk":        session.recovery_risk,
        },
        "report":  session.report_json,
        "answers": [
            {
                "question_id":   a.question_id,
                "question_text": a.question_text,
                "typed_answer":  a.typed_answer,
                "transcript":    a.transcript,
                "audio_url":     a.audio_url,
            }
            for a in session.answers
        ],
        "audio_files": [
            {
                "question_id": af.question_id,
                "file_name":   af.file_name,
                "audio_url":   f"/uploads/audio/{session_id}/{af.file_name}",
                "size_bytes":  af.size_bytes,
            }
            for af in session.audio_files
        ],
    }


# ── Download PDF ──────────────────────────────────────────────────────────────

@router.get("/{session_id}/report.pdf")
def download_report_pdf(session_id: str, db: Session = Depends(get_db)):
    session = db.query(AssessmentSession).filter(AssessmentSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if not session.completed_at or not session.report_json:
        raise HTTPException(status_code=409, detail="Session not yet completed")

    pdf_bytes = _generate_pdf(session)
    safe = (session.client_name or "client").replace(" ", "-").lower()
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="ergocare-{safe}-{session_id[:8]}.pdf"'},
    )


# ── PDF generator ─────────────────────────────────────────────────────────────

def _generate_pdf(session: AssessmentSession) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    except ImportError:
        raise HTTPException(status_code=500, detail="reportlab not installed — run: pip install reportlab")

    report = session.report_json
    W = A4[0] - 40 * mm

    # ── Colours ───────────────────────────────────────────────────────────────
    TEAL      = colors.HexColor("#01696f")
    TEAL_DARK = colors.HexColor("#005f73")
    RED       = colors.HexColor("#c1121f")
    AMBER     = colors.HexColor("#d97706")
    GREEN     = colors.HexColor("#2a9d8f")
    LIGHT     = colors.HexColor("#f4f9f7")
    WHITE     = colors.white
    GREY      = colors.HexColor("#6b7a99")
    BORDER    = colors.HexColor("#d4d1ca")

    level       = report.get("level", "Unknown")
    lv_color    = RED if level == "High" else AMBER if level == "Moderate" else GREEN
    overall     = session.overall_risk or 0

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=18*mm, bottomMargin=18*mm)
    styles = getSampleStyleSheet()

    def sty(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    title_s   = sty("T",  fontSize=24, textColor=TEAL_DARK, fontName="Helvetica-Bold", spaceAfter=2)
    sub_s     = sty("S",  fontSize=10, textColor=GREY, spaceAfter=10)
    sec_s     = sty("H",  fontSize=12, textColor=TEAL_DARK, fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=5)
    body_s    = sty("B",  fontSize=9,  leading=14, spaceAfter=3)
    bullet_s  = sty("BL", fontSize=9,  leading=14, leftIndent=10, spaceAfter=3)
    pos_s     = sty("P",  fontSize=9,  leading=14, leftIndent=10, textColor=GREEN, spaceAfter=3)
    badge_s   = sty("BD", fontSize=13, textColor=WHITE, fontName="Helvetica-Bold", alignment=TA_CENTER)
    small_s   = sty("SM", fontSize=8,  textColor=GREY, spaceAfter=1)
    right_s   = sty("R",  fontSize=9,  textColor=GREY, alignment=TA_RIGHT)
    q_s       = sty("Q",  fontSize=8,  textColor=TEAL_DARK, fontName="Helvetica-Bold", spaceAfter=2)
    a_s       = sty("A",  fontSize=8,  textColor=colors.HexColor("#334155"), spaceAfter=4, leftIndent=8)

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    hdr = Table([[Paragraph("ErgoCare AI", title_s),
                  Paragraph("Ergonomic Risk Assessment Report", right_s)]],
                colWidths=[W*0.6, W*0.4])
    hdr.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"BOTTOM"),
                              ("BOTTOMPADDING",(0,0),(-1,-1),4)]))
    story.append(hdr)
    story.append(HRFlowable(width="100%", thickness=1.5, color=TEAL, spaceAfter=10))

    # ── Risk badge ────────────────────────────────────────────────────────────
    badge = Table([[Paragraph(f"Overall Risk: {level}  —  {overall:.0f}%", badge_s)]],
                  colWidths=[W])
    badge.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,-1), lv_color),
                                ("TOPPADDING",(0,0),(-1,-1),10),
                                ("BOTTOMPADDING",(0,0),(-1,-1),10),
                                ("ROUNDEDCORNERS",[5])]))
    story.append(badge)
    story.append(Spacer(1, 10))

    # ── Client info ───────────────────────────────────────────────────────────
    if session.client_name:
        story.append(Paragraph("Client Information", sec_s))
        cdata = [
            ["Name",    session.client_name  or "—", "Email",   session.client_email or "—"],
            ["Phone",   session.client_phone or "—", "Age",     str(session.client_age or "—")],
            ["Job Role",session.client_job   or "—", "Session", session.id[:12] + "…"],
        ]
        ctbl = Table([[Paragraph(str(v), small_s if i%2==0 else body_s) for i,v in enumerate(row)] for row in cdata],
                     colWidths=[25*mm, W/2-25*mm-2*mm, 22*mm, W/2-22*mm-2*mm])
        ctbl.setStyle(TableStyle([
            ("FONTNAME",(0,0),(0,-1),"Helvetica-Bold"),("FONTNAME",(2,0),(2,-1),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,-1),8),("TEXTCOLOR",(0,0),(0,-1),GREY),("TEXTCOLOR",(2,0),(2,-1),GREY),
            ("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4),
            ("GRID",(0,0),(-1,-1),0.3,BORDER),("BACKGROUND",(0,0),(-1,-1),LIGHT),
        ]))
        story.append(ctbl)
        story.append(Spacer(1, 6))

    # ── Meta ─────────────────────────────────────────────────────────────────
    completed = session.completed_at.strftime("%d %B %Y, %H:%M UTC") if session.completed_at else "N/A"
    story.append(Paragraph(f"Completed: {completed}  ·  Mode: {session.input_mode.capitalize()}  ·  Session: {session.id[:16]}…", small_s))
    story.append(Spacer(1, 8))

    # ── Score breakdown table ─────────────────────────────────────────────────
    story.append(Paragraph("Risk Score Breakdown", sec_s))
    score_rows = [
        [Paragraph("Category", sty("TH", fontSize=9, textColor=WHITE, fontName="Helvetica-Bold")),
         Paragraph("Score",    sty("TH2",fontSize=9, textColor=WHITE, fontName="Helvetica-Bold", alignment=TA_CENTER)),
         Paragraph("Level",    sty("TH3",fontSize=9, textColor=WHITE, fontName="Helvetica-Bold", alignment=TA_CENTER))],
    ]
    score_data = [
        ("Overall Risk",         session.overall_risk),
        ("Posture & Movement",   session.posture_risk),
        ("Eye Strain",           session.eye_strain),
        ("Workload Stress",      session.workload_stress),
        ("Body Discomfort",      session.musculoskeletal_risk),
        ("Recovery & Sleep",     session.recovery_risk),
    ]
    for label, val in score_data:
        v = val or 0
        lv = "High" if v >= 70 else "Moderate" if v >= 40 else "Low"
        c  = RED if lv=="High" else AMBER if lv=="Moderate" else GREEN
        bar = "█" * int(v / 5)
        score_rows.append([
            Paragraph(label, body_s),
            Paragraph(f"{bar}  <b>{v:.0f}%</b>", sty(f"SB{label}", fontSize=8, textColor=c, leading=12)),
            Paragraph(lv, sty(f"LV{label}", fontSize=9, textColor=c, fontName="Helvetica-Bold", alignment=TA_CENTER)),
        ])
    stbl = Table(score_rows, colWidths=[55*mm, 85*mm, 28*mm])
    stbl.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),TEAL_DARK),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[LIGHT, WHITE]),
        ("GRID",(0,0),(-1,-1),0.3,BORDER),
        ("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5),
        ("LEFTPADDING",(0,0),(-1,-1),6),
    ]))
    story.append(stbl)
    story.append(Spacer(1, 8))

    # ── Top factors ───────────────────────────────────────────────────────────
    if report.get("top_factors"):
        story.append(Paragraph("Top Risk Factors", sec_s))
        for f in report["top_factors"]:
            story.append(Paragraph(f"▸  {f}", bullet_s))
        story.append(Spacer(1, 4))

    # ── Detailed findings ─────────────────────────────────────────────────────
    if report.get("detailed_findings"):
        story.append(Paragraph("Detailed Findings & Recommendations", sec_s))
        for f in report["detailed_findings"]:
            story.append(Paragraph(f"•  {f}", bullet_s))
        story.append(Spacer(1, 4))

    # ── Positive habits ───────────────────────────────────────────────────────
    if report.get("positive_habits"):
        story.append(Paragraph("Positive Habits Detected", sec_s))
        for p in report["positive_habits"]:
            story.append(Paragraph(f"✓  {p}", pos_s))
        story.append(Spacer(1, 4))

    # ── Action plan ───────────────────────────────────────────────────────────
    if report.get("action_plan"):
        story.append(Paragraph("Prioritised Action Plan", sec_s))
        for i, a in enumerate(report["action_plan"], 1):
            story.append(Paragraph(f"{i}.  {a}", bullet_s))
        story.append(Spacer(1, 8))

    # ── All 40 Q&A answers ────────────────────────────────────────────────────
    if session.answers:
        story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))
        story.append(Paragraph("All 40 Answers", sec_s))
        for ans in sorted(session.answers, key=lambda x: x.question_id):
            val = ans.typed_answer or ans.transcript or "—"
            audio_note = f"  🎙 Audio recorded" if ans.audio_url else ""
            story.append(Paragraph(f"Q{ans.question_id}. {ans.question_text}", q_s))
            story.append(Paragraph(f"→ {val}{audio_note}", a_s))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceBefore=10, spaceAfter=4))
    story.append(Paragraph(
        "This report is generated by ErgoCare AI and is for informational purposes only. "
        "Consult a qualified healthcare or occupational health professional for clinical advice. "
        f"Generated: {datetime.now(timezone.utc).strftime('%d %B %Y, %H:%M UTC')}",
        sty("FT", fontSize=7.5, textColor=GREY, spaceBefore=2),
    ))

    doc.build(story)
    return buffer.getvalue()
