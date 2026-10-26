"""ReportLab (BSD) renderer. Built-in Helvetica uses WinAnsi, which covers Spanish accents."""

from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from xeon.application.ports.quote_pdf import QuotePdfDocument

LEGEND_COLOR = colors.HexColor("#b3261e")


class ReportlabQuotePdfRenderer:
    def render(self, document: QuotePdfDocument) -> bytes:
        buffer = io.BytesIO()
        title = f"Cotización {document.number} v{document.version}"
        # invariant=1 fixes dates and ids so the same document renders to the same bytes.
        pdf = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=18 * mm,
            rightMargin=18 * mm,
            topMargin=16 * mm,
            bottomMargin=16 * mm,
            title=title,
            author=document.store_name,
            invariant=1,
        )
        styles = getSampleStyleSheet()
        body = styles["BodyText"]
        heading = styles["Heading1"]
        legend = ParagraphStyle(
            "legend", parent=body, textColor=LEGEND_COLOR, fontName="Helvetica-Bold", fontSize=11
        )

        def text(value: str, style: ParagraphStyle = body) -> Paragraph:
            return Paragraph(escape(value), style)

        story: list[object] = [
            text(document.legend, legend),
            Spacer(1, 4 * mm),
            Paragraph(escape(document.store_name), heading),
            *[text(item) for item in document.store_details],
            Spacer(1, 3 * mm),
            text(
                f"Cotización {document.number} · versión {document.version} · "
                f"emitida el {document.issued_on}"
            ),
            text(f"Estado: {document.status_label}"),
            Spacer(1, 4 * mm),
        ]
        rows = [["Producto", "Cantidad", "Precio unitario", "Subtotal"]]
        rows += [
            [text(line.description), line.quantity, line.unit_price, line.subtotal]
            for line in document.lines
        ]
        rows.append(["", "", "TOTAL", f"{document.total} {document.currency}"])
        table = Table(rows, colWidths=[80 * mm, 28 * mm, 34 * mm, 34 * mm], repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#14213d")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.grey),
                    ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black),
                ]
            )
        )
        story += [table, Spacer(1, 5 * mm)]
        story += [
            text(f"Entrega: {document.delivery}"),
            text(f"Sede: {document.branch}"),
            text(f"Forma de pago: {document.payment}"),
            text(f"Vigencia: {document.validity}"),
            text(document.tax_note),
            Spacer(1, 6 * mm),
            text(document.legend, legend),
        ]
        pdf.build(story)
        return buffer.getvalue()
