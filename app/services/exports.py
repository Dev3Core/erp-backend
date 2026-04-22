"""CSV / PDF exports. Small focused module — heavy aggregations live in MetricsService."""

import csv
import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models.liquidation import Liquidation


def liquidations_to_csv(rows: list[Liquidation]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "id",
            "shift_id",
            "period_date",
            "gross_usd",
            "net_usd",
            "cop_amount",
            "trm_used",
            "status",
            "notes",
            "created_at",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                str(r.id),
                str(r.shift_id),
                r.period_date.isoformat(),
                str(r.gross_usd),
                str(r.net_usd),
                str(r.cop_amount),
                str(r.trm_used),
                r.status.value if hasattr(r.status, "value") else str(r.status),
                (r.notes or "").replace("\n", " "),
                r.created_at.isoformat(),
            ]
        )
    return buf.getvalue().encode("utf-8")


def liquidations_to_pdf(
    rows: list[Liquidation],
    *,
    studio_name: str,
    period_from: date | None,
    period_to: date | None,
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="Liquidations Report")
    styles = getSampleStyleSheet()

    elements: list = []
    elements.append(Paragraph(f"Liquidations — {studio_name}", styles["Title"]))
    period = (
        f"Period: {period_from or '...'}  →  {period_to or '...'}"
        if (period_from or period_to)
        else "Period: all"
    )
    elements.append(Paragraph(period, styles["Normal"]))
    elements.append(Spacer(1, 12))

    header = [
        "Period",
        "Gross USD",
        "Net USD",
        "COP",
        "TRM",
        "Status",
    ]
    data = [header]
    for r in rows:
        data.append(
            [
                r.period_date.isoformat(),
                f"{r.gross_usd}",
                f"{r.net_usd}",
                f"{r.cop_amount}",
                f"{r.trm_used}",
                r.status.value if hasattr(r.status, "value") else str(r.status),
            ]
        )
    table = Table(data, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#333333")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]
        )
    )
    elements.append(table)

    doc.build(elements)
    return buf.getvalue()
