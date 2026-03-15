"""
PDF Generator — professional invoices & receipts.
Supports 4 page sizes and 4 visual styles.
"""

import os
import tempfile
from datetime import datetime
from reportlab.lib.pagesizes import A4, A5, LETTER, LEGAL
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

# ── Page sizes ────────────────────────────────────────────────────────────────
PAGE_SIZES = {"A4": A4, "A5": A5, "Letter": LETTER, "Legal": LEGAL}
PAGE_SIZE_LABELS = {
    "A4":     "A4 (210×297 mm)",
    "A5":     "A5 (148×210 mm)",
    "Letter": "US Letter (8.5×11 in)",
    "Legal":  "US Legal (8.5×14 in)",
}

# ── PDF Styles ────────────────────────────────────────────────────────────────
PDF_STYLES = {
    "classic":    "Classic Blue",
    "dark":       "Executive Dark",
    "minimal":    "Clean Minimal",
    "elegant":    "Elegant Green",
}

CURRENCIES = {
    "USD": "$", "EUR": "€", "GBP": "£", "TRY": "₺",
    "AED": "AED ", "SAR": "SAR ", "IQD": "IQD "
}

# ── Colour themes ─────────────────────────────────────────────────────────────
THEMES = {
    "classic": {
        "primary":   colors.HexColor("#1565C0"),
        "secondary": colors.HexColor("#00897B"),
        "header_bg": colors.HexColor("#0D1B2A"),
        "light_bg":  colors.HexColor("#F5F7FA"),
        "stripe":    colors.HexColor("#EEF2F7"),
        "text":      colors.HexColor("#1A1A2E"),
        "grey":      colors.HexColor("#78909C"),
        "divider":   colors.HexColor("#CFD8DC"),
        "total_bg":  colors.HexColor("#1565C0"),
        "corner":    colors.HexColor("#E8EEF7"),
    },
    "dark": {
        "primary":   colors.HexColor("#212121"),
        "secondary": colors.HexColor("#B8860B"),
        "header_bg": colors.HexColor("#1A1A1A"),
        "light_bg":  colors.HexColor("#F8F8F8"),
        "stripe":    colors.HexColor("#F0F0F0"),
        "text":      colors.HexColor("#1A1A1A"),
        "grey":      colors.HexColor("#757575"),
        "divider":   colors.HexColor("#DDDDDD"),
        "total_bg":  colors.HexColor("#212121"),
        "corner":    colors.HexColor("#ECECEC"),
    },
    "minimal": {
        "primary":   colors.HexColor("#333333"),
        "secondary": colors.HexColor("#333333"),
        "header_bg": colors.HexColor("#FFFFFF"),
        "light_bg":  colors.HexColor("#FAFAFA"),
        "stripe":    colors.HexColor("#F5F5F5"),
        "text":      colors.HexColor("#222222"),
        "grey":      colors.HexColor("#888888"),
        "divider":   colors.HexColor("#E0E0E0"),
        "total_bg":  colors.HexColor("#333333"),
        "corner":    colors.HexColor("#F5F5F5"),
    },
    "elegant": {
        "primary":   colors.HexColor("#2E7D32"),
        "secondary": colors.HexColor("#1B5E20"),
        "header_bg": colors.HexColor("#1B5E20"),
        "light_bg":  colors.HexColor("#F1F8E9"),
        "stripe":    colors.HexColor("#E8F5E9"),
        "text":      colors.HexColor("#1A1A1A"),
        "grey":      colors.HexColor("#6A6A6A"),
        "divider":   colors.HexColor("#C8E6C9"),
        "total_bg":  colors.HexColor("#2E7D32"),
        "corner":    colors.HexColor("#E8F5E9"),
    },
}


class InvoiceCanvas(canvas.Canvas):
    def __init__(self, *args, inv_type="Invoice", page_w=None, page_h=None,
                 theme=None, style_key="classic", **kwargs):
        super().__init__(*args, **kwargs)
        self._inv_type  = inv_type
        self._page_w    = page_w or A4[0]
        self._page_h    = page_h or A4[1]
        self._theme     = theme or THEMES["classic"]
        self._style_key = style_key
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self._draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def _draw_page_decorations(self, total_pages):
        W, H  = self._page_w, self._page_h
        T     = self._theme
        style = self._style_key

        if style == "minimal":
            # Clean minimal: just a thin top line and bottom line
            self.setStrokeColor(T["primary"])
            self.setLineWidth(2)
            self.line(0, H, W, H - 1)
            self.setLineWidth(1)
            self.line(20*mm, H - 6*mm, W - 20*mm, H - 6*mm)
        elif style == "dark":
            # Full dark header bar
            self.setFillColor(T["header_bg"])
            self.rect(0, H - 10*mm, W, 10*mm, fill=1, stroke=0)
            self.setFillColor(T["secondary"])
            self.rect(0, H - 11.5*mm, W, 1.5*mm, fill=1, stroke=0)
            # Side accent strip
            self.setFillColor(colors.HexColor("#2A2A2A"))
            self.rect(0, 0, 4*mm, H, fill=1, stroke=0)
        elif style == "elegant":
            # Green header bar
            self.setFillColor(T["header_bg"])
            self.rect(0, H - 9*mm, W, 9*mm, fill=1, stroke=0)
            self.setFillColor(T["secondary"])
            self.rect(0, H - 10.5*mm, W, 1.5*mm, fill=1, stroke=0)
            # Bottom green bar
            self.setFillColor(T["primary"])
            self.rect(0, 0, W, 5*mm, fill=1, stroke=0)
        else:  # classic
            self.setFillColor(T["primary"])
            self.rect(0, H - 8*mm, W, 8*mm, fill=1, stroke=0)
            self.setFillColor(T["secondary"])
            self.rect(0, H - 10*mm, W, 2*mm, fill=1, stroke=0)
            # Corner decoration
            self.saveState()
            self.setFillColor(T["corner"])
            path = self.beginPath()
            path.moveTo(W * 0.72, H)
            path.lineTo(W, H)
            path.lineTo(W, H * 0.72)
            path.close()
            self.drawPath(path, fill=1, stroke=0)
            self.restoreState()

        # Footer line
        self.setStrokeColor(T["divider"])
        self.setLineWidth(0.5)
        self.line(20*mm, 14*mm, W - 20*mm, 14*mm)
        # Footer: left = blank / confidential, right = page number
        self.setFillColor(T["grey"])
        self.setFont("Helvetica", 7.5)
        self.drawString(20*mm, 10*mm, "Confidential")
        self.drawRightString(W - 20*mm, 10*mm, f"Page {self._pageNumber} of {total_pages}")


def _sym(inv):
    return CURRENCIES.get(inv.get("currency", "USD"), "$")

def _fmt(amount, inv):
    return f"{_sym(inv)}{amount:,.2f}"

def _calc(inv):
    items    = inv.get("items", [])
    subtotal = sum(i["qty"] * i["price"] for i in items)
    disc_pct = inv.get("discount", 0)
    tax_pct  = inv.get("tax_rate", 0)
    disc_amt = subtotal * disc_pct / 100
    taxable  = subtotal - disc_amt
    tax_amt  = taxable  * tax_pct  / 100
    total    = taxable  + tax_amt
    return subtotal, disc_pct, disc_amt, tax_pct, tax_amt, total

def _styles(scale=1.0, T=None):
    if T is None:
        T = THEMES["classic"]
    def s(base): return max(6, int(base * scale))
    return {
        "doc_type":          ParagraphStyle("doc_type",          fontName="Helvetica-Bold",        fontSize=s(26), textColor=colors.white,  alignment=TA_RIGHT),
        "doc_number":        ParagraphStyle("doc_number",        fontName="Helvetica",             fontSize=s(11), textColor=colors.HexColor("#B0BEC5"), alignment=TA_RIGHT),
        "company_name":      ParagraphStyle("company_name",      fontName="Helvetica-Bold",        fontSize=s(14), textColor=T["header_bg"], spaceAfter=2),
        "company_info":      ParagraphStyle("company_info",      fontName="Helvetica",             fontSize=s(8),  textColor=T["grey"],      leading=s(13)),
        "section_label":     ParagraphStyle("section_label",     fontName="Helvetica-Bold",        fontSize=s(7),  textColor=T["grey"],      spaceAfter=2, letterSpacing=1.0),
        "client_name":       ParagraphStyle("client_name",       fontName="Helvetica-Bold",        fontSize=s(12), textColor=T["text"],      spaceAfter=3),
        "client_info":       ParagraphStyle("client_info",       fontName="Helvetica",             fontSize=s(8),  textColor=T["grey"],      leading=s(13)),
        "meta_label":        ParagraphStyle("meta_label",        fontName="Helvetica-Bold",        fontSize=s(7),  textColor=T["grey"]),
        "meta_value":        ParagraphStyle("meta_value",        fontName="Helvetica",             fontSize=s(8),  textColor=T["text"]),
        "table_header":      ParagraphStyle("table_header",      fontName="Helvetica-Bold",        fontSize=s(8),  textColor=colors.white),
        "table_cell":        ParagraphStyle("table_cell",        fontName="Helvetica",             fontSize=s(8),  textColor=T["text"],      leading=s(12)),
        "table_cell_right":  ParagraphStyle("table_cell_right",  fontName="Helvetica",             fontSize=s(8),  textColor=T["text"],      alignment=TA_RIGHT),
        "total_label":       ParagraphStyle("total_label",       fontName="Helvetica-Bold",        fontSize=s(9),  textColor=T["text"],      alignment=TA_RIGHT),
        "total_value":       ParagraphStyle("total_value",       fontName="Helvetica",             fontSize=s(9),  textColor=T["text"],      alignment=TA_RIGHT),
        "grand_label":       ParagraphStyle("grand_label",       fontName="Helvetica-Bold",        fontSize=s(12), textColor=colors.white,   alignment=TA_RIGHT),
        "grand_value":       ParagraphStyle("grand_value",       fontName="Helvetica-Bold",        fontSize=s(13), textColor=colors.white,   alignment=TA_RIGHT),
        "notes_label":       ParagraphStyle("notes_label",       fontName="Helvetica-Bold",        fontSize=s(8),  textColor=T["primary"],   spaceAfter=3),
        "notes_text":        ParagraphStyle("notes_text",        fontName="Helvetica",             fontSize=s(8),  textColor=T["grey"],      leading=s(13)),
        "paid_stamp":        ParagraphStyle("paid_stamp",        fontName="Helvetica-Bold",        fontSize=s(30), textColor=colors.HexColor("#C8E6C9"), alignment=TA_CENTER),
        "thank_you":         ParagraphStyle("thank_you",         fontName="Helvetica-BoldOblique", fontSize=s(9),  textColor=T["secondary"], alignment=TA_CENTER),
        "minimal_company":   ParagraphStyle("minimal_company",   fontName="Helvetica-Bold",        fontSize=s(16), textColor=T["text"],      spaceAfter=2),
    }


def generate_invoice_pdf(inv: dict) -> str:
    page_key  = inv.get("page_size", "A4")
    style_key = inv.get("pdf_style", "classic")
    page_size = PAGE_SIZES.get(page_key, A4)
    W, H      = page_size
    T         = THEMES.get(style_key, THEMES["classic"])
    inv_type  = inv.get("type", "Invoice")
    company   = inv.get("company", {})
    sym       = _sym(inv)
    scale     = 0.78 if page_key == "A5" else 1.0
    S         = _styles(scale, T)
    mg        = 18*mm if page_key == "A5" else 20*mm
    tm        = 26*mm if page_key == "A5" else 28*mm

    tmp  = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    path = tmp.name
    tmp.close()

    doc   = SimpleDocTemplate(path, pagesize=page_size,
                              leftMargin=mg, rightMargin=mg,
                              topMargin=tm, bottomMargin=20*mm)
    dw    = doc.width
    story = []

    def ph(text, sk):
        return Paragraph(str(text), S[sk])

    # ── HEADER ────────────────────────────────────────────────────────────────
    if style_key == "minimal":
        # Minimal: company name left, doc type right in dark text on white
        company_block = [
            ph(company.get("name","Your Company"), "minimal_company"),
        ]
        for field in ("address","email","phone"):
            v = company.get(field,"")
            if v: company_block.append(ph(v.replace("\n","<br/>"), "company_info"))
        if company.get("website"): company_block.append(ph(company["website"], "company_info"))
        if company.get("tax_id"):  company_block.append(ph(f"Tax ID: {company['tax_id']}", "company_info"))

        doc_block_style = ParagraphStyle("dt_min", fontName="Helvetica-Bold",
                                         fontSize=int(26*scale), textColor=T["primary"], alignment=TA_RIGHT)
        num_style = ParagraphStyle("dn_min", fontName="Helvetica",
                                   fontSize=int(11*scale), textColor=T["grey"], alignment=TA_RIGHT)
        doc_block = [Paragraph(inv_type.upper(), doc_block_style),
                     Paragraph(f"#{inv.get('number','0001')}", num_style)]
        hdr = Table([[company_block, doc_block]], colWidths=[dw*0.55, dw*0.45])
        hdr.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),
                                 ("LINEBELOW",(0,0),(-1,0),1.5,T["primary"])]))
    else:
        # Coloured header block
        company_block = [ph(company.get("name","Your Company"), "company_name")]
        for field in ("address","email","phone"):
            v = company.get(field,"")
            if v: company_block.append(ph(v.replace("\n","<br/>"), "company_info"))
        if company.get("website"): company_block.append(ph(company["website"], "company_info"))
        if company.get("tax_id"):  company_block.append(ph(f"Tax ID: {company['tax_id']}", "company_info"))

        doc_block = [ph(inv_type.upper(),"doc_type"), ph(f"#{inv.get('number','0001')}","doc_number")]
        hdr = Table([[company_block, doc_block]], colWidths=[dw*0.55, dw*0.45])
        hdr.setStyle(TableStyle([
            ("BACKGROUND",    (1,0),(1,0), T["header_bg"]),
            ("VALIGN",        (0,0),(-1,-1),"TOP"),
            ("ALIGN",         (1,0),(1,0),"RIGHT"),
            ("TOPPADDING",    (1,0),(1,0),10),
            ("BOTTOMPADDING", (1,0),(1,0),10),
            ("RIGHTPADDING",  (1,0),(1,0),12),
            ("LEFTPADDING",   (1,0),(1,0),8),
        ]))

    story += [hdr, Spacer(1, 5*mm)]

    # ── BILL TO + META ────────────────────────────────────────────────────────
    client_block = [ph("BILL TO","section_label"), ph(inv.get("client_name","—"),"client_name")]
    for field in ("client_address","client_email","client_phone"):
        v = inv.get(field,"")
        if v: client_block.append(ph(v.replace("\n","<br/>"), "client_info"))

    meta_rows = [
        [ph("DATE ISSUED","meta_label"), ph(inv.get("date","—"),      "meta_value")],
        [ph("DUE DATE",   "meta_label"), ph(inv.get("due_date","—"),  "meta_value")],
        [ph("CURRENCY",   "meta_label"), ph(inv.get("currency","USD"),"meta_value")],
    ]
    if company.get("tax_id"):
        meta_rows.append([ph("TAX ID","meta_label"), ph(company["tax_id"],"meta_value")])

    meta_tbl = Table(meta_rows, colWidths=[26*mm*scale, 38*mm*scale])
    meta_tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[T["light_bg"], T["stripe"]]),
        ("TOPPADDING",    (0,0),(-1,-1),3),
        ("BOTTOMPADDING", (0,0),(-1,-1),3),
        ("LEFTPADDING",   (0,0),(-1,-1),5),
        ("RIGHTPADDING",  (0,0),(-1,-1),5),
    ]))

    info = Table([[client_block,"",meta_tbl]], colWidths=[dw*0.44, dw*0.04, dw*0.52])
    info.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"),("ALIGN",(2,0),(2,0),"RIGHT")]))
    story += [info, Spacer(1, 6*mm)]

    # ── LINE ITEMS ────────────────────────────────────────────────────────────
    cn=dw*0.04; cd=dw*0.37; cu=dw*0.09; cq=dw*0.10; cp=dw*0.18; ct=dw*0.20
    headers = [ph("#","table_header"), ph("DESCRIPTION","table_header"),
               ph("UNIT","table_header"), ph("QTY","table_header"),
               ph("UNIT PRICE","table_header"), ph("AMOUNT","table_header")]
    rows = [headers]
    for idx, item in enumerate(inv.get("items",[]), 1):
        lt = item["qty"] * item["price"]
        rows.append([
            ph(str(idx),                    "table_cell"),
            ph(item.get("name",""),         "table_cell"),
            ph(item.get("unit","pc"),       "table_cell"),
            ph(f'{item["qty"]:g}',          "table_cell_right"),
            ph(f'{sym}{item["price"]:,.2f}',"table_cell_right"),
            ph(f'{sym}{lt:,.2f}',           "table_cell_right"),
        ])

    stripe = [("BACKGROUND",(0,i),(-1,i), T["light_bg"] if i%2==0 else colors.white)
              for i in range(1,len(rows))]
    pad = 6 if page_key != "A5" else 4

    items_tbl = Table(rows, colWidths=[cn,cd,cu,cq,cp,ct], repeatRows=1)
    items_tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  T["header_bg"]),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,0),  8*scale),
        ("TOPPADDING",    (0,0),(-1,0),  pad+2),
        ("BOTTOMPADDING", (0,0),(-1,0),  pad+2),
        ("ALIGN",         (3,0),(-1,0),  "RIGHT"),
        ("ALIGN",         (3,1),(-1,-1), "RIGHT"),
        ("FONTNAME",      (0,1),(-1,-1), "Helvetica"),
        ("FONTSIZE",      (0,1),(-1,-1), 8*scale),
        ("TOPPADDING",    (0,1),(-1,-1), pad),
        ("BOTTOMPADDING", (0,1),(-1,-1), pad),
        ("LEFTPADDING",   (0,0),(-1,-1), 6),
        ("RIGHTPADDING",  (0,0),(-1,-1), 6),
        ("LINEBELOW",     (0,0),(-1,0),  0.5, T["secondary"]),
        ("LINEBELOW",     (0,1),(-1,-1), 0.3, T["divider"]),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        *stripe,
    ]))
    story += [items_tbl, Spacer(1, 4*mm)]

    # ── TOTALS ────────────────────────────────────────────────────────────────
    subtotal, disc_pct, disc_amt, tax_pct, tax_amt, total = _calc(inv)

    tot_rows = [[ph("Subtotal","total_label"), ph(_fmt(subtotal,inv),"total_value")]]
    if disc_pct:
        tot_rows.append([ph(f"Discount ({disc_pct:g}%)","total_label"),
                         ph(f"- {_fmt(disc_amt,inv)}","total_value")])
    if tax_pct:
        tot_rows.append([ph(f"Tax ({tax_pct:g}%)","total_label"),
                         ph(f"+ {_fmt(tax_amt,inv)}","total_value")])

    tot_tbl = Table(tot_rows, colWidths=[dw*0.65, dw*0.35])
    tot_tbl.setStyle(TableStyle([
        ("ALIGN",(0,0),(-1,-1),"RIGHT"),
        ("TOPPADDING",(0,0),(-1,-1),3),
        ("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LINEBELOW",(0,-1),(-1,-1),0.5,T["divider"]),
    ]))
    story += [tot_tbl, Spacer(1, 2*mm)]

    grand = Table([[ph(f"TOTAL {inv.get('currency','USD')}","grand_label"),
                    ph(_fmt(total,inv),"grand_value")]],
                  colWidths=[dw*0.65, dw*0.35])
    grand.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0), T["total_bg"]),
        ("ALIGN",(0,0),(-1,-1),"RIGHT"),
        ("TOPPADDING",(0,0),(-1,-1),9),
        ("BOTTOMPADDING",(0,0),(-1,-1),9),
        ("LEFTPADDING",(0,0),(-1,-1),12),
        ("RIGHTPADDING",(0,0),(-1,-1),12),
    ]))
    story += [grand, Spacer(1, 5*mm)]

    # PAID stamp for receipts
    if inv_type == "Receipt":
        paid_bg = colors.HexColor("#2E7D32")
        paid = Table([[ph("PAID","paid_stamp")]], colWidths=[dw])
        paid.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(0,0), paid_bg),
            ("TOPPADDING",(0,0),(0,0),5),
            ("BOTTOMPADDING",(0,0),(0,0),5),
        ]))
        story += [paid, Spacer(1, 4*mm)]

    # ── NOTES ─────────────────────────────────────────────────────────────────
    notes = inv.get("notes","")
    if notes:
        story.append(HRFlowable(width="100%", thickness=0.5, color=T["divider"]))
        story.append(Spacer(1, 3*mm))
        story.append(ph("NOTES & PAYMENT TERMS","notes_label"))
        story.append(ph(notes.replace("\n","<br/>"),"notes_text"))
        story.append(Spacer(1, 4*mm))

    # ── THANK YOU ─────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=T["divider"]))
    story.append(Spacer(1, 4*mm))
    thank = "Thank you for your business!" if inv_type=="Invoice" else "Thank you for your payment!"
    story.append(ph(thank,"thank_you"))

    # ── BUILD ──────────────────────────────────────────────────────────────────
    def make_canvas(filename, **kwargs):
        return InvoiceCanvas(filename, inv_type=inv_type,
                             page_w=W, page_h=H, theme=T, style_key=style_key, **kwargs)

    doc.build(story, canvasmaker=make_canvas)
    return path
