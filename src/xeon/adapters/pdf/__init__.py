"""PDF adapters. Importing this package never imports the PDF library."""

from __future__ import annotations

from xeon.application.ports.quote_pdf import QuotePdfRenderer


def load_pdf_renderer() -> QuotePdfRenderer | None:
    """Return the ReportLab renderer, or None when the optional `pdf` group is not installed."""
    try:
        from xeon.adapters.pdf.reportlab_renderer import ReportlabQuotePdfRenderer
    except ImportError:
        return None
    return ReportlabQuotePdfRenderer()
