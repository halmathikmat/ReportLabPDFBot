"""
PDF Generator v5 — ground-up redesign.
Clean, modern, professional layout.
4 themes, 4 page sizes.
"""

import os
import tempfile
from datetime import datetime
from reportlab.lib.pagesizes import A4, A5, LETTER, LEGAL
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, Flowable
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

PAGE_SIZES = {"A4": A4, "A5": A5, "Letter": LETTER, "Legal": LEGAL}
PAGE_SIZE_LABELS = {
    "A4":     "A4 (210×297 mm)",
    "A5":     "A5 (148×210 mm)",
    "Letter": "US Letter (8.5×11 in)",
    "Legal":  "US Legal (8.5×14 in)",
}
PDF_STYLES = {
    "classic": "Classic Blue",
    "dark":    "Executive Dark",
    "minimal": "Clean Minimal",
    "elegant": "Elegant Green",
}
CURRENCIES = {
    "USD":"$","EUR":"€","GBP":"£","TRY":"₺",
    "AED":"AED ","SAR":"SAR ","IQD":"IQD "
}

# ── Themes ────────────────────────────────────────────────────────────────────
T = {
    "classic": dict(
        bar=colors.HexColor("#1A237E"),
        bar2=colors.HexColor("#283593"),
        accent=colors.HexColor("#1565C0"),
        badge=colors.HexColor("#1565C0"),
        badge_text=colors.white,
        num_text=colors.HexColor("#5C6BC0"),
        total_bg=colors.HexColor("#1565C0"),
        total_text=colors.white,
        paid_bg=colors.HexColor("#1B5E20"),
        paid_text=colors.white,
        table_head=colors.HexColor("#1A237E"),
        row_even=colors.HexColor("#EEF2FF"),
        row_odd=colors.white,
        divider=colors.HexColor("#C5CAE9"),
        meta_bg=colors.HexColor("#E8EAF6"),
        meta_alt=colors.HexColor("#F3F4FB"),
        co_name=colors.HexColor("#1A237E"),
        co_info=colors.HexColor("#5C6BC0"),
        cl_name=colors.HexColor("#1A1A1A"),
        cl_info=colors.HexColor("#757575"),
        body=colors.HexColor("#212121"),
        grey=colors.HexColor("#9E9E9E"),
        notes_label=colors.HexColor("#1565C0"),
        thanks=colors.HexColor("#1565C0"),
    ),
    "dark": dict(
        bar=colors.HexColor("#111111"),
        bar2=colors.HexColor("#222222"),
        accent=colors.HexColor("#CFB53B"),
        badge=colors.HexColor("#111111"),
        badge_text=colors.HexColor("#CFB53B"),
        num_text=colors.HexColor("#888888"),
        total_bg=colors.HexColor("#111111"),
        total_text=colors.white,
        paid_bg=colors.HexColor("#1B5E20"),
        paid_text=colors.white,
        table_head=colors.HexColor("#222222"),
        row_even=colors.HexColor("#F5F5F5"),
        row_odd=colors.white,
        divider=colors.HexColor("#DDDDDD"),
        meta_bg=colors.HexColor("#F5F5F5"),
        meta_alt=colors.HexColor("#EEEEEE"),
        co_name=colors.HexColor("#111111"),
        co_info=colors.HexColor("#555555"),
        cl_name=colors.HexColor("#111111"),
        cl_info=colors.HexColor("#757575"),
        body=colors.HexColor("#111111"),
        grey=colors.HexColor("#999999"),
        notes_label=colors.HexColor("#111111"),
        thanks=colors.HexColor("#CFB53B"),
    ),
    "minimal": dict(
        bar=colors.HexColor("#F5F5F5"),
        bar2=colors.HexColor("#E0E0E0"),
        accent=colors.HexColor("#212121"),
        badge=colors.HexColor("#212121"),
        badge_text=colors.white,
        num_text=colors.HexColor("#9E9E9E"),
        total_bg=colors.HexColor("#212121"),
        total_text=colors.white,
        paid_bg=colors.HexColor("#212121"),
        paid_text=colors.white,
        table_head=colors.HexColor("#212121"),
        row_even=colors.HexColor("#FAFAFA"),
        row_odd=colors.white,
        divider=colors.HexColor("#E0E0E0"),
        meta_bg=colors.HexColor("#FAFAFA"),
        meta_alt=colors.HexColor("#F5F5F5"),
        co_name=colors.HexColor("#212121"),
        co_info=colors.HexColor("#757575"),
        cl_name=colors.HexColor("#212121"),
        cl_info=colors.HexColor("#757575"),
        body=colors.HexColor("#212121"),
        grey=colors.HexColor("#9E9E9E"),
        notes_label=colors.HexColor("#212121"),
        thanks=colors.HexColor("#757575"),
    ),
    "elegant": dict(
        bar=colors.HexColor("#1B5E20"),
        bar2=colors.HexColor("#2E7D32"),
        accent=colors.HexColor("#388E3C"),
        badge=colors.HexColor("#1B5E20"),
        badge_text=colors.white,
        num_text=colors.HexColor("#66BB6A"),
        total_bg=colors.HexColor("#1B5E20"),
        total_text=colors.white,
        paid_bg=colors.HexColor("#1B5E20"),
        paid_text=colors.white,
        table_head=colors.HexColor("#1B5E20"),
        row_even=colors.HexColor("#F1F8E9"),
        row_odd=colors.white,
        divider=colors.HexColor("#C8E6C9"),
        meta_bg=colors.HexColor("#F1F8E9"),
        meta_alt=colors.HexColor("#E8F5E9"),
        co_name=colors.HexColor("#1B5E20"),
        co_info=colors.HexColor("#388E3C"),
        cl_name=colors.HexColor("#1A1A1A"),
        cl_info=colors.HexColor("#757575"),
        body=colors.HexColor("#1A1A1A"),
        grey=colors.HexColor("#9E9E9E"),
        notes_label=colors.HexColor("#1B5E20"),
        thanks=colors.HexColor("#2E7D32"),
    ),
}


# ── Custom Flowables ──────────────────────────────────────────────────────────

class PaidBadge(Flowable):
    """A perfectly sized PAID badge drawn on canvas."""
    def __init__(self, width, bg, text_color, font_size=18):
        super().__init__()
        self.width  = width
        self.height = font_size * 2.2
        self.bg     = bg
        self.tc     = text_color
        self.fs     = font_size

    def draw(self):
        c = self.canv
        # Background
        c.setFillColor(self.bg)
        c.roundRect(0, 0, self.width, self.height, 2*mm, fill=1, stroke=0)
        # Centered text
        c.setFillColor(self.tc)
        c.setFont("Helvetica-Bold", self.fs)
        c.drawCentredString(self.width / 2, (self.height - self.fs * 0.72) / 2, "PAID")


class TopBanner(Flowable):
    """Full-width top banner with doc type badge + number."""
    def __init__(self, page_w, page_h, left_m, right_m, top_m,
                 inv_type, number, theme, style_key):
        super().__init__()
        self.pw       = page_w
        self.ph       = page_h
        self.lm       = left_m
        self.rm       = right_m
        self.tm       = top_m
        self.inv_type = inv_type
        self.number   = number
        self.th       = theme
        self.sk       = style_key
        self.width    = page_w - left_m - right_m
        self.height   = 0  # drawn on canvas, not in flow

    def draw(self):
        pass  # all drawing done in InvoiceCanvas


class InvoiceCanvas(canvas.Canvas):
    def __init__(self, *args, inv=None, pw=None, ph=None,
                 lm=20*mm, rm=20*mm, tm=20*mm, style_key="classic", **kwargs):
        super().__init__(*args, **kwargs)
        self._inv   = inv or {}
        self._pw    = pw or A4[0]
        self._ph    = ph or A4[1]
        self._lm    = lm
        self._rm    = rm
        self._tm    = tm
        self._sk    = style_key
        self._th    = T.get(style_key, T["classic"])
        self._saved = []

    def showPage(self):
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for state in self._saved:
            self.__dict__.update(state)
            self._draw(total)
            super().showPage()
        super().save()

    def _draw(self, total):
        W, H   = self._pw, self._ph
        th     = self._th
        sk     = self._sk
        lm, rm = self._lm, self._rm
        inv    = self._inv
        doc_type = inv.get("type", "Invoice").upper()
        number   = inv.get("number", "")

        # ── Top banner ────────────────────────────────────────────────────────
        banner_h = 22 * mm
        self.setFillColor(th["bar"])
        self.rect(0, H - banner_h, W, banner_h, fill=1, stroke=0)

        # Accent strip at bottom of banner
        self.setFillColor(th["accent"])
        self.setLineWidth(0)
        self.rect(0, H - banner_h - 1.5*mm, W, 1.5*mm, fill=1, stroke=0)

        # ── Doc type badge inside banner ──────────────────────────────────────
        badge_fs   = 15
        badge_pad  = 4 * mm
        badge_text = doc_type
        self.setFont("Helvetica-Bold", badge_fs)
        badge_tw = self.stringWidth(badge_text, "Helvetica-Bold", badge_fs)
        badge_w  = badge_tw + badge_pad * 2
        badge_h  = 10 * mm
        badge_x  = W - rm - badge_w
        badge_y  = H - banner_h + (banner_h - badge_h) / 2

        self.setFillColor(th["badge"])
        self.setStrokeColor(th["badge_text"])
        self.setLineWidth(1)
        self.roundRect(badge_x, badge_y, badge_w, badge_h, 1.5*mm, fill=1, stroke=1)
        self.setFillColor(th["badge_text"])
        self.drawCentredString(badge_x + badge_w/2,
                               badge_y + (badge_h - badge_fs*0.72)/2,
                               badge_text)

        # ── Number below banner ───────────────────────────────────────────────
        self.setFillColor(th["num_text"])
        self.setFont("Helvetica", 8)
        num_str = f"# {number}"
        self.drawRightString(W - rm, H - banner_h - 5.5*mm, num_str)

        # ── Footer ────────────────────────────────────────────────────────────
        self.setStrokeColor(th["divider"])
        self.setLineWidth(0.4)
        self.line(lm, 13*mm, W - rm, 13*mm)
        self.setFillColor(th["grey"])
        self.setFont("Helvetica", 7)
        self.drawRightString(W - rm, 9*mm, f"Page {self._pageNumber} of {total}")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sym(inv): return CURRENCIES.get(inv.get("currency","USD"),"$")
def _fmt(n,inv): return f"{_sym(inv)}{n:,.2f}"
def _calc(inv):
    items    = inv.get("items",[])
    sub      = sum(i["qty"]*i["price"] for i in items)
    dp, tp   = inv.get("discount",0), inv.get("tax_rate",0)
    da       = sub*dp/100
    tax      = (sub-da)*tp/100
    return sub, dp, da, tp, tax, sub-da+tax

def _st(name, **kw):
    return ParagraphStyle(name, **kw)

def _styles(sc, th):
    def s(b): return max(6, int(b*sc))
    W = colors.white
    return {
        "co_name":   _st("co_name",   fontName="Helvetica-Bold",        fontSize=s(13), textColor=th["co_name"],     spaceAfter=1),
        "co_info":   _st("co_info",   fontName="Helvetica",             fontSize=s(8),  textColor=th["co_info"],     leading=s(12)),
        "sec":       _st("sec",       fontName="Helvetica-Bold",        fontSize=s(7),  textColor=th["grey"],        spaceAfter=2, letterSpacing=0.8),
        "cl_name":   _st("cl_name",   fontName="Helvetica-Bold",        fontSize=s(11), textColor=th["cl_name"],     spaceAfter=2),
        "cl_info":   _st("cl_info",   fontName="Helvetica",             fontSize=s(8),  textColor=th["cl_info"],     leading=s(12)),
        "ml":        _st("ml",        fontName="Helvetica-Bold",        fontSize=s(7),  textColor=th["grey"]),
        "mv":        _st("mv",        fontName="Helvetica",             fontSize=s(8),  textColor=th["body"]),
        "th":        _st("th",        fontName="Helvetica-Bold",        fontSize=s(8),  textColor=W),
        "td":        _st("td",        fontName="Helvetica",             fontSize=s(8),  textColor=th["body"],        leading=s(11)),
        "td_r":      _st("td_r",      fontName="Helvetica",             fontSize=s(8),  textColor=th["body"],        alignment=TA_RIGHT),
        "tl":        _st("tl",        fontName="Helvetica-Bold",        fontSize=s(9),  textColor=th["body"],        alignment=TA_RIGHT),
        "tv":        _st("tv",        fontName="Helvetica",             fontSize=s(9),  textColor=th["body"],        alignment=TA_RIGHT),
        "gl":        _st("gl",        fontName="Helvetica-Bold",        fontSize=s(11), textColor=W,                 alignment=TA_RIGHT),
        "gv":        _st("gv",        fontName="Helvetica-Bold",        fontSize=s(12), textColor=W,                 alignment=TA_RIGHT),
        "nl":        _st("nl",        fontName="Helvetica-Bold",        fontSize=s(8),  textColor=th["notes_label"], spaceAfter=2),
        "nt":        _st("nt",        fontName="Helvetica",             fontSize=s(8),  textColor=th["grey"],        leading=s(12)),
        "ty":        _st("ty",        fontName="Helvetica-BoldOblique", fontSize=s(9),  textColor=th["thanks"],      alignment=TA_CENTER),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def generate_invoice_pdf(inv: dict) -> str:
    pk   = inv.get("page_size","A4")
    sk   = inv.get("pdf_style","classic")
    ps   = PAGE_SIZES.get(pk, A4)
    PW,PH= ps
    th   = T.get(sk, T["classic"])
    itype= inv.get("type","Invoice")
    comp = inv.get("company",{})
    sym  = _sym(inv)
    sc   = 0.78 if pk=="A5" else 1.0
    S    = _styles(sc, th)

    lm   = 16*mm if pk=="A5" else 18*mm
    rm   = lm
    # top margin: banner(22mm) + accent(1.5mm) + number_row(6mm) + gap(6mm)
    tm   = 38*mm
    bm   = 18*mm

    tmp  = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    path = tmp.name; tmp.close()

    doc  = SimpleDocTemplate(path, pagesize=ps,
                             leftMargin=lm, rightMargin=rm,
                             topMargin=tm, bottomMargin=bm)
    dw   = doc.width
    story= []

    def ph(txt, st): return Paragraph(str(txt), S[st])

    # ── Company + meta block ──────────────────────────────────────────────────
    co_block = [ph(comp.get("name","Your Company"),"co_name")]
    for f in ("address","email","phone"):
        v = comp.get(f,"")
        if v: co_block.append(ph(v.replace("\n","<br/>"),"co_info"))
    if comp.get("website"): co_block.append(ph(comp["website"],"co_info"))
    if comp.get("tax_id"):  co_block.append(ph(f"Tax ID: {comp['tax_id']}","co_info"))

    meta_data = [
        [ph("ISSUED",   "ml"), ph(inv.get("date","—"),      "mv")],
        [ph("DUE",      "ml"), ph(inv.get("due_date","—"),  "mv")],
        [ph("CURRENCY", "ml"), ph(inv.get("currency","USD"),"mv")],
    ]
    if comp.get("tax_id"):
        meta_data.append([ph("TAX ID","ml"), ph(comp["tax_id"],"mv")])

    meta_tbl = Table(meta_data, colWidths=[18*mm*sc, 36*mm*sc])
    meta_tbl.setStyle(TableStyle([
        ("ROWBACKGROUNDS",(0,0),(-1,-1),[th["meta_bg"],th["meta_alt"]]),
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LEFTPADDING",   (0,0),(-1,-1), 4),
        ("RIGHTPADDING",  (0,0),(-1,-1), 4),
        ("LINEBELOW",     (0,0),(-1,-1), 0.3, th["divider"]),
    ]))

    top_row = Table([[co_block, meta_tbl]], colWidths=[dw*0.55, dw*0.45])
    top_row.setStyle(TableStyle([
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("ALIGN", (1,0),(1,0),  "RIGHT"),
    ]))
    story += [top_row, Spacer(1, 6*mm)]

    # ── Divider ───────────────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=th["divider"]))
    story.append(Spacer(1, 5*mm))

    # ── Bill To + Date meta ───────────────────────────────────────────────────
    cl_block = [ph("BILL TO","sec"), ph(inv.get("client_name","—"),"cl_name")]
    for f in ("client_address","client_email","client_phone"):
        v = inv.get(f,"")
        if v: cl_block.append(ph(v.replace("\n","<br/>"),"cl_info"))

    story.append(Table([[cl_block]], colWidths=[dw]))
    story.append(Spacer(1, 6*mm))

    # ── Line items ────────────────────────────────────────────────────────────
    cw = [dw*0.04, dw*0.36, dw*0.09, dw*0.10, dw*0.19, dw*0.20]
    hdr = [ph("#","th"),ph("DESCRIPTION","th"),ph("UNIT","th"),
           ph("QTY","th"),ph("UNIT PRICE","th"),ph("AMOUNT","th")]
    rows = [hdr]
    for i, item in enumerate(inv.get("items",[]), 1):
        lt = item["qty"]*item["price"]
        rows.append([
            ph(str(i),                    "td"),
            ph(item.get("name",""),       "td"),
            ph(item.get("unit","pc"),     "td"),
            ph(f'{item["qty"]:g}',        "td_r"),
            ph(f'{sym}{item["price"]:,.2f}',"td_r"),
            ph(f'{sym}{lt:,.2f}',         "td_r"),
        ])

    stripe = [("BACKGROUND",(0,r),(-1,r), th["row_even"] if r%2==1 else th["row_odd"])
              for r in range(1,len(rows))]
    pad = 5 if pk!="A5" else 3

    it = Table(rows, colWidths=cw, repeatRows=1)
    it.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,0),  th["table_head"]),
        ("FONTNAME",      (0,0),(-1,0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0,0),(-1,0),  8*sc),
        ("TOPPADDING",    (0,0),(-1,0),  pad+2),("BOTTOMPADDING",(0,0),(-1,0),pad+2),
        ("ALIGN",         (3,0),(-1,-1), "RIGHT"),
        ("FONTNAME",      (0,1),(-1,-1), "Helvetica"),
        ("FONTSIZE",      (0,1),(-1,-1), 8*sc),
        ("TOPPADDING",    (0,1),(-1,-1), pad),("BOTTOMPADDING",(0,1),(-1,-1),pad),
        ("LEFTPADDING",   (0,0),(-1,-1), 5),("RIGHTPADDING",(0,0),(-1,-1),5),
        ("LINEBELOW",     (0,0),(-1,0),  1, th["accent"]),
        ("LINEBELOW",     (0,1),(-1,-1), 0.3, th["divider"]),
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        *stripe,
    ]))
    story += [it, Spacer(1,5*mm)]

    # ── Totals ────────────────────────────────────────────────────────────────
    sub, dp, da, tp, tax, total = _calc(inv)

    tot = [[ph("Subtotal","tl"),ph(_fmt(sub,inv),"tv")]]
    if dp: tot.append([ph(f"Discount ({dp:g}%)","tl"),ph(f"- {_fmt(da,inv)}","tv")])
    if tp: tot.append([ph(f"Tax ({tp:g}%)","tl"),    ph(f"+ {_fmt(tax,inv)}","tv")])

    tt = Table(tot, colWidths=[dw*0.68, dw*0.32])
    tt.setStyle(TableStyle([
        ("ALIGN",(0,0),(-1,-1),"RIGHT"),
        ("TOPPADDING",(0,0),(-1,-1),3),("BOTTOMPADDING",(0,0),(-1,-1),3),
        ("LINEBELOW",(0,-1),(-1,-1),0.5,th["divider"]),
    ]))
    story += [tt, Spacer(1,2*mm)]

    gt = Table(
        [[ph(f"TOTAL  {inv.get('currency','USD')}","gl"), ph(_fmt(total,inv),"gv")]],
        colWidths=[dw*0.60, dw*0.40]
    )
    gt.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),th["total_bg"]),
        ("ALIGN",(0,0),(-1,-1),"RIGHT"),
        ("TOPPADDING",(0,0),(-1,-1),9),("BOTTOMPADDING",(0,0),(-1,-1),9),
        ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
        ("ROUNDEDCORNERS",[3]),
    ]))
    story += [gt, Spacer(1,5*mm)]

    # ── PAID badge ────────────────────────────────────────────────────────────
    if itype == "Receipt":
        story.append(PaidBadge(dw, th["paid_bg"], th["paid_text"], font_size=int(18*sc)))
        story.append(Spacer(1,5*mm))

    # ── Notes ─────────────────────────────────────────────────────────────────
    notes = inv.get("notes","")
    if notes:
        story += [
            HRFlowable(width="100%", thickness=0.4, color=th["divider"]),
            Spacer(1,3*mm),
            ph("NOTES & PAYMENT TERMS","nl"),
            ph(notes.replace("\n","<br/>"),"nt"),
            Spacer(1,4*mm),
        ]

    # ── Thank you ─────────────────────────────────────────────────────────────
    story += [
        HRFlowable(width="100%", thickness=0.4, color=th["divider"]),
        Spacer(1,4*mm),
        ph("Thank you for your business!" if itype=="Invoice" else "Thank you for your payment!","ty"),
    ]

    def make_canvas(filename, **kwargs):
        return InvoiceCanvas(filename, inv=inv, pw=PW, ph=PH,
                             lm=lm, rm=rm, tm=tm, style_key=sk, **kwargs)

    doc.build(story, canvasmaker=make_canvas)
    return path
