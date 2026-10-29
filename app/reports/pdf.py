"""Business PDF report: every section of a full analysis, laid out plainly.

Structure first, styling later (design pass). Uses ReportLab with bundled DejaVu Sans so
symbols in reviews (★, −, “ ”) render.
"""

from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.shapes import Drawing, Line, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

FONTS = Path(__file__).parent / "fonts"
_registered = False

INK = colors.HexColor("#171717")
MUTED = colors.HexColor("#6e6e76")
LINE = colors.HexColor("#e2e2de")
SOFT = colors.HexColor("#f6f6f4")
POS = colors.HexColor("#15803d")
NEG = colors.HexColor("#b42318")
WARN = colors.HexColor("#b54708")

VERDICTS = {
    "improved": ("Improved", POS),
    "worse": ("Got worse", NEG),
    "no_significant_change": ("No significant change", MUTED),
    "inconclusive": ("Inconclusive", WARN),
    "not_enough_data": ("Not enough data yet", MUTED),
    "unknown_aspect": ("Aspect not found in reviews", MUTED),
}


def _fonts() -> None:
    global _registered
    if not _registered:
        pdfmetrics.registerFont(TTFont("Body", str(FONTS / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("Body-Bold", str(FONTS / "DejaVuSans-Bold.ttf")))
        pdfmetrics.registerFontFamily("Body", normal="Body", bold="Body-Bold")
        _registered = True


def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle(
        "body", fontName="Body", fontSize=9.5, leading=13.5, textColor=INK, alignment=TA_LEFT
    )
    return {
        "body": base,
        "muted": ParagraphStyle("muted", parent=base, textColor=MUTED, fontSize=8.5, leading=12),
        "small": ParagraphStyle("small", parent=base, fontSize=8, leading=11),
        "quote": ParagraphStyle(
            "quote", parent=base, leftIndent=8, textColor=colors.HexColor("#3f3f46"), fontSize=9
        ),
        "h1": ParagraphStyle("h1", parent=base, fontName="Body-Bold", fontSize=22, leading=27, spaceAfter=6),
        "h2": ParagraphStyle(
            "h2",
            parent=base,
            fontName="Body-Bold",
            fontSize=14,
            leading=18,
            spaceBefore=10,
            spaceAfter=6,
            keepWithNext=1,  # a heading never sits alone at the bottom of a page
        ),
        "h3": ParagraphStyle(
            "h3",
            parent=base,
            fontName="Body-Bold",
            fontSize=10.5,
            leading=14,
            spaceBefore=6,
            spaceAfter=3,
            keepWithNext=1,
        ),
        "kpi": ParagraphStyle("kpi", parent=base, fontName="Body-Bold", fontSize=16, leading=20),
    }


def _p(text, style) -> Paragraph:
    return Paragraph(escape(str(text)), style)


def _pct(x, digits=0) -> str:
    return "–" if x is None else f"{x * 100:.{digits}f}%"


def _date(s) -> str:
    if not s:
        return "–"
    try:
        return (date.fromisoformat(s[:10])).strftime("%d %b %Y")
    except ValueError:
        return str(s)


def _table(rows, widths, header=True, zebra=True) -> Table:
    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0, hAlign="LEFT")
    style = [
        ("FONT", (0, 0), (-1, -1), "Body", 8.5),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if header:
        style += [("FONT", (0, 0), (-1, 0), "Body-Bold", 8), ("TEXTCOLOR", (0, 0), (-1, 0), MUTED)]
    if zebra:
        style += [("ROWBACKGROUNDS", (0, 1 if header else 0), (-1, -1), [colors.white, SOFT])]
    t.setStyle(TableStyle(style))
    return t


def _quotes(quotes, st) -> list:
    out = []
    for q in quotes or []:
        meta = " · ".join(
            x
            for x in (
                f"{q['rating']:g}★" if q.get("rating") is not None else None,
                _date(q.get("date")) if q.get("date") else None,
                q.get("source"),
            )
            if x
        )
        out.append(
            Paragraph(
                f"“{escape(q['text'])}” <font color='#6e6e76' size='7.5'>{escape(meta)}</font>", st["quote"]
            )
        )
    return out


def _trend_chart(
    weeks: list[dict], mark: str | None = None, width=170 * mm, height=45 * mm
) -> Drawing | None:
    """4-week rolling share of reviews complaining about one aspect."""
    pts = []
    for i, w in enumerate(weeks):
        window = weeks[max(0, i - 3) : i + 1]
        n = sum(x["reviews"] for x in window)
        if n >= 3:
            pts.append(
                (date.fromisoformat(w["week"]).toordinal(), 100 * sum(x["negative"] for x in window) / n)
            )
    if len(pts) < 3:
        return None
    d = Drawing(width, height)
    lp = LinePlot()
    lp.x, lp.y, lp.width, lp.height = 28, 16, width - 40, height - 26
    lp.data = [pts]
    lp.lines[0].strokeColor = INK
    lp.lines[0].strokeWidth = 1.2
    lp.xValueAxis.valueMin, lp.xValueAxis.valueMax = pts[0][0], pts[-1][0]
    lp.xValueAxis.visibleLabels = False
    lp.xValueAxis.strokeColor = LINE
    lp.yValueAxis.valueMin = 0
    lp.yValueAxis.valueMax = max(5, max(p[1] for p in pts) * 1.15)
    lp.yValueAxis.labels.fontName = "Body"
    lp.yValueAxis.labels.fontSize = 6.5
    lp.yValueAxis.labelTextFormat = "%d%%"
    lp.yValueAxis.strokeColor = LINE
    d.add(lp)
    d.add(
        String(
            28,
            2,
            date.fromordinal(pts[0][0]).strftime("%b %Y"),
            fontName="Body",
            fontSize=6.5,
            fillColor=MUTED,
        )
    )
    d.add(
        String(
            width - 12,
            2,
            date.fromordinal(pts[-1][0]).strftime("%b %Y"),
            fontName="Body",
            fontSize=6.5,
            fillColor=MUTED,
            textAnchor="end",
        )
    )
    if mark:
        m = date.fromisoformat(mark[:10]).toordinal()
        if pts[0][0] <= m <= pts[-1][0]:
            x = lp.x + (m - pts[0][0]) / (pts[-1][0] - pts[0][0] or 1) * lp.width
            d.add(
                Line(x, lp.y, x, lp.y + lp.height, strokeColor=MUTED, strokeDashArray=[2, 2], strokeWidth=0.6)
            )
            d.add(
                String(x + 2, lp.y + lp.height - 6, "change", fontName="Body", fontSize=6.5, fillColor=MUTED)
            )
    return d


def render_report_pdf(report: dict, product: dict, organization: str) -> bytes:
    """Build the full business report as PDF bytes."""
    _fonts()
    st = _styles()
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"{product.get('name')} review report",
        author="ReviewPulse",
    )
    W = doc.width
    story: list = []
    o = report.get("overall") or {}
    trends = {t["aspect"]: t["weeks"] for t in report.get("trends", [])}

    # ---------------------------------------------------------------- cover
    story += [
        _p("ReviewPulse · Customer review report", st["muted"]),
        Spacer(1, 30 * mm),
        _p(product.get("name", "Product"), st["h1"]),
        _p(" · ".join(x for x in (product.get("brand"), product.get("category")) if x) or " ", st["muted"]),
        Spacer(1, 10 * mm),
        _table(
            [
                ["Prepared for", organization],
                ["Report type", "Full report" if report.get("kind") == "full" else "Quick report"],
                ["Reviews analysed", f"{report.get('review_count', 0):,}"],
                [
                    "Period covered",
                    f"{_date((report.get('period') or {}).get('from'))} to {_date((report.get('period') or {}).get('to'))}",
                ],
                [
                    "Generated",
                    (
                        datetime.fromisoformat(report["generated_at"]).strftime("%d %b %Y, %H:%M UTC")
                        if report.get("generated_at")
                        else "–"
                    ),
                ],
                ["Analysis ID", report.get("analysis_id", "–")],
            ],
            [45 * mm, W - 45 * mm],
            header=False,
        ),
        PageBreak(),
    ]

    # ---------------------------------------------------------------- 1 summary
    story.append(_p("1. Executive summary", st["h2"]))
    story += [Paragraph(f"• {escape(s)}", st["body"]) for s in report.get("summary", [])]
    story.append(Spacer(1, 4 * mm))
    if o:
        kpis = [
            ("Sentiment score", f"{o.get('sentiment_score', 0):+d}", "−100 to +100"),
            ("Positive reviews", _pct(o.get("positive_share")), f"{report.get('review_count', 0):,} reviews"),
            (
                "Average rating",
                f"{o['average_rating']:.2f}★" if o.get("average_rating") else "–",
                f"{o.get('rated_reviews', 0):,} rated",
            ),
            ("Issues found", str(len(report.get("lacking", []))), "with 3+ complaints"),
        ]
        cells = [
            [
                Paragraph(
                    f"<font color='#6e6e76' size='7.5'>{escape(k.upper())}</font><br/>"
                    f"<font name='Body-Bold' size='15'>{escape(v)}</font><br/>"
                    f"<font color='#6e6e76' size='7.5'>{escape(sub)}</font>",
                    st["body"],
                )
                for k, v, sub in kpis
            ]
        ]
        t = Table(cells, colWidths=[W / 4] * 4, hAlign="LEFT")
        t.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.4, LINE),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(t)

    # ---------------------------------------------------------------- 2 warnings
    alerts = report.get("alerts") or []
    story.append(_p("2. Early warnings", st["h2"]))
    if not alerts:
        story.append(
            _p("No aspect's complaint rate is currently rising significantly above its baseline.", st["body"])
        )
    for a in alerts:
        story.append(
            KeepTogether(
                [
                    Paragraph(
                        f"<font color='#b54708'><b>{escape(a['aspect'].capitalize())}</b></font>", st["h3"]
                    ),
                    _p(
                        f"Complaints rose to {_pct(a['current_rate'])} of recent reviews ({a['complaints']} of {a['reviews']}), "
                        f"from a baseline of {_pct(a['baseline_rate'])}, starting {_date(a['first_seen'])} (p = {a['p_value']:.4f}).",
                        st["body"],
                    ),
                    *_quotes(a.get("quotes"), st),
                ]
            )
        )

    # ---------------------------------------------------------------- 3 what to fix
    lacking = report.get("lacking") or []
    story.append(_p("3. What to fix first", st["h2"]))
    story.append(
        _p(
            "Ranked by estimated average-rating cost: the gap between reviews without the aspect and reviews "
            "complaining about it, times the share complaining.",
            st["muted"],
        )
    )
    if lacking:
        rows = [["#", "Aspect", "Complaints", "Of all reviews", "Negative rate", "Rating cost"]]
        for i, s in enumerate(lacking, 1):
            rows.append(
                [
                    str(i),
                    s["aspect"].capitalize(),
                    f"{s['negative']:,}",
                    _pct(s["negative_share"], 1),
                    _pct(s["negative_rate"]),
                    f"−{s['rating_impact']:.2f}★" if s.get("rating_impact") else "–",
                ]
            )
        story.append(_table(rows, [8 * mm, 60 * mm, 24 * mm, 28 * mm, 26 * mm, W - 146 * mm]))
        for i, s in enumerate(lacking, 1):
            block = [_p(f"{i}. {s['aspect'].capitalize()}", st["h3"])]
            if s.get("specific_issues"):
                block.append(
                    _p(
                        "Specifically: "
                        + ", ".join(f"{x['name']} ({x['mentions']})" for x in s["specific_issues"]),
                        st["body"],
                    )
                )
            block += _quotes(s.get("quotes"), st)
            story.append(KeepTogether(block))
    else:
        story.append(_p("No recurring complaints were found.", st["body"]))

    # ---------------------------------------------------------------- 4 fix verification
    section4 = [_p("4. Did your fixes work?", st["h2"])]
    fvs = report.get("fix_verification") or []
    if not fvs:
        story += section4
        story.append(
            _p(
                "No product changes have been logged. Log each change you ship so its effect on complaints can be measured.",
                st["body"],
            )
        )
    for fv in fvs:
        # The change's heading travels with its first result so it never ends a page alone.
        heading = section4 + [_p(f"{fv['description']} — shipped {_date(fv['changed_on'])}", st["h3"])]
        section4 = []
        for r in fv["results"]:
            label, color = VERDICTS.get(r.get("verdict"), (r.get("verdict"), MUTED))
            rows = [
                ["Aspect", (r.get("aspect") or r.get("requested") or "").capitalize()],
                [
                    "Verdict",
                    Paragraph(f"<font color='{color.hexval()}'><b>{escape(label)}</b></font>", st["body"]),
                ],
            ]
            if r.get("before_rate") is not None:
                rows += [
                    [
                        "Complaint rate",
                        f"{_pct(r['before_rate'], 1)} before ({r.get('reviews_before', 0):,} reviews) → "
                        f"{_pct(r['after_rate'], 1)} after ({r.get('reviews_after', 0):,} reviews)",
                    ],
                ]
            if r.get("relative_change") is not None:
                ci = (
                    f", 95% CI {r['ci_low'] * 100:+.0f}% to {r['ci_high'] * 100:+.0f}%"
                    if r.get("ci_low") is not None
                    else ""
                )
                rows.append(["Effect", f"{r['relative_change'] * 100:+.0f}%{ci}, p = {r['p_value']:.3f}"])
            if r.get("method"):
                rows.append(["Method", r["method"]])
            if r.get("note"):
                rows.append(["Note", Paragraph(escape(r["note"]), st["small"])])
            block = heading + [_table(rows, [32 * mm, W - 32 * mm], header=False, zebra=False)]
            heading = []
            chart = (
                _trend_chart(trends.get(r.get("aspect")) or [], mark=fv["changed_on"])
                if r.get("aspect")
                else None
            )
            if chart:
                block += [
                    Spacer(1, 2 * mm),
                    chart,
                    _p("Share of reviews complaining, 4-week rolling. Dashed line: the change.", st["muted"]),
                ]
            story.append(KeepTogether(block + [Spacer(1, 4 * mm)]))

    # ---------------------------------------------------------------- 5 every aspect
    aspects = report.get("aspects") or []
    if aspects:
        story.append(PageBreak())
        story.append(_p("5. Every aspect customers mention", st["h2"]))
        rows = [["Aspect", "Mentions", "Positive", "Negative", "Share", "Neg. rate", "Rating cost"]]
        for s in aspects:
            rows.append(
                [
                    s["aspect"].capitalize() + (" *" if s.get("discovered") else ""),
                    f"{s['mentions']:,}",
                    f"{s['positive']:,}",
                    f"{s['negative']:,}",
                    _pct(s["share"], 1),
                    _pct(s["negative_rate"]),
                    f"−{s['rating_impact']:.2f}★" if s.get("rating_impact") else "–",
                ]
            )
        story.append(_table(rows, [56 * mm, 20 * mm, 18 * mm, 19 * mm, 17 * mm, 19 * mm, W - 149 * mm]))
        story.append(
            _p(
                "* Issue discovered from the reviews themselves rather than from the standard aspect list.",
                st["muted"],
            )
        )
        for s in aspects:
            qs = (s.get("negative_quotes") or []) + (s.get("positive_quotes") or [])
            if qs:
                story.append(KeepTogether([_p(s["aspect"].capitalize(), st["h3"]), *_quotes(qs, st)]))

    # ---------------------------------------------------------------- 6 trends
    if report.get("trends"):
        story.append(_p("6. Complaint trends", st["h2"]))
        for t in report["trends"][:6]:
            chart = _trend_chart(t["weeks"], height=38 * mm)
            if chart:
                story.append(KeepTogether([_p(t["aspect"].capitalize(), st["h3"]), chart]))

    # ---------------------------------------------------------------- 7 strengths
    story.append(_p("7. What customers love", st["h2"]))
    for s in report.get("strengths") or []:
        story.append(
            KeepTogether(
                [
                    _p(f"{s['aspect'].capitalize()} — {s['positive']:,} positive mentions", st["h3"]),
                    *_quotes(s.get("quotes"), st),
                ]
            )
        )
    if not report.get("strengths"):
        story.append(_p("No aspect has consistently more praise than complaints yet.", st["body"]))

    # ---------------------------------------------------------------- 8 sources & method
    story.append(_p("8. Data and methodology", st["h2"]))
    if report.get("sources"):
        story.append(
            _table(
                [["Source", "Reviews"]] + [[s["source"], f"{s['reviews']:,}"] for s in report["sources"]],
                [60 * mm, 30 * mm],
            )
        )
        story.append(Spacer(1, 3 * mm))
    for k, v in (report.get("methodology") or {}).items():
        story.append(
            Paragraph(f"<b>{escape(k.replace('_', ' ').capitalize())}:</b> {escape(str(v))}", st["small"])
        )
    story.append(Spacer(1, 3 * mm))
    story.append(
        _p(
            "Limitations: estimates of rating cost are associations, not proof of cause. A steady decline in "
            "complaints that was already under way can occasionally be credited to a change; read each verdict "
            "with its chart. Reviewer names and contact details are never stored.",
            st["muted"],
        )
    )

    def footer(canvas, doc_):
        canvas.saveState()
        canvas.setFont("Body", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 10 * mm, f"{product.get('name', '')} · ReviewPulse report")
        canvas.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Page {doc_.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buf.getvalue()
