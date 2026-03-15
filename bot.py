"""
Invoice & Receipt Generator Telegram Bot
=========================================
Features:
  - 4 PDF page sizes: A4, A5, US Letter, US Legal
  - Free tier: 5 invoices/receipts total
  - Pro tier: unlimited (50 Telegram Stars, or discounted price)
  - Admin: create limited-time discount campaigns + broadcast to free users

Setup:
  1. pip install -r requirements.txt
  2. Set BOT_TOKEN and ADMIN_IDS in config.py
  3. python bot.py
"""

import logging
import os
import asyncio
from datetime import datetime, timezone, timedelta
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    LabeledPrice,
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, ContextTypes,
    PreCheckoutQueryHandler, filters,
)
from pdf_generator import generate_invoice_pdf, PAGE_SIZE_LABELS, PDF_STYLES
from database import Database, FREE_LIMIT

logging.basicConfig(
    format="%(asctime)s │ %(levelname)s │ %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Conversation states ───────────────────────────────────────────────────────
MAIN_MENU             = 0
SETUP_COMPANY_NAME    = 1
SETUP_COMPANY_ADDRESS = 2
SETUP_COMPANY_EMAIL   = 3
SETUP_COMPANY_PHONE   = 4
SETUP_COMPANY_WEBSITE = 5
SETUP_COMPANY_TAX_ID  = 6
INV_CLIENT_NAME       = 7
INV_CLIENT_ADDRESS    = 8
INV_CLIENT_EMAIL      = 9
INV_CLIENT_PHONE      = 10
INV_NUMBER            = 11
INV_DATE              = 12
INV_DUE_DATE          = 13
INV_CURRENCY          = 14
INV_PAGE_SIZE         = 15
INV_TAX_RATE          = 16
INV_DISCOUNT          = 17
ITEM_NAME             = 18
ITEM_UNIT             = 19
ITEM_QTY              = 20
ITEM_PRICE            = 21
CONFIRM_ITEM          = 22
ADDING_ITEMS          = 23
INV_NOTES             = 24
REVIEW_INVOICE        = 25
ADMIN_MENU            = 26
ADMIN_DISC_STARS      = 27
ADMIN_DISC_HOURS      = 28
ADMIN_BROADCAST_MSG   = 29

CURRENCIES = {
    "USD": "$", "EUR": "€", "GBP": "£", "TRY": "₺",
    "AED": "AED ", "SAR": "SAR ", "IQD": "IQD "
}

PRO_BASE_PRICE = 50   # stars (no discount)

db = Database()


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _admin_ids():
    try:
        from config import ADMIN_IDS
        return ADMIN_IDS if isinstance(ADMIN_IDS, list) else [ADMIN_IDS]
    except Exception:
        return []

def _is_admin(user_id: int) -> bool:
    return user_id in _admin_ids()

def main_menu_keyboard(user_id: int):
    plan = db.get_user_plan(user_id)
    allowed, remaining = db.can_create_invoice(user_id)
    if plan == "pro":
        usage_line = "✨ Pro — Unlimited"
    else:
        usage_line = f"🆓 Free — {remaining}/{FREE_LIMIT} remaining"

    rows = [
        [InlineKeyboardButton("🧾 New Invoice", callback_data="new_invoice"),
         InlineKeyboardButton("📋 New Receipt", callback_data="new_receipt")],
        [InlineKeyboardButton("📁 My Documents", callback_data="my_invoices"),
         InlineKeyboardButton("🏢 My Company",   callback_data="my_company")],
        [InlineKeyboardButton("💱 Currency",      callback_data="currency_settings"),
         InlineKeyboardButton("📐 Page Size",     callback_data="pagesize_settings")],
        [InlineKeyboardButton(f"⭐ Upgrade to Pro  ({usage_line})", callback_data="upgrade_pro")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")],
    ]
    if _is_admin(user_id):
        rows.append([InlineKeyboardButton("🔧 Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(rows)

def back_kb(back_to="main_menu"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Back", callback_data=back_to)]])

def yes_no_kb():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Yes", callback_data="yes"),
        InlineKeyboardButton("❌ No",  callback_data="no"),
    ]])

def fmt_cur(amount: float, sym: str) -> str:
    return f"{sym}{amount:,.2f}"

def invoice_summary(inv: dict) -> str:
    sym      = CURRENCIES.get(inv.get("currency","USD"), "$")
    items    = inv.get("items",[])
    subtotal = sum(i["qty"]*i["price"] for i in items)
    disc     = inv.get("discount", 0)
    tax      = inv.get("tax_rate", 0)
    d_amt    = subtotal * disc / 100
    taxable  = subtotal - d_amt
    t_amt    = taxable  * tax  / 100
    total    = taxable  + t_amt
    items_str = "\n".join(
        f"  • {it['name']} × {it['qty']} {it.get('unit','pc')} @ {sym}{it['price']:.2f}"
        for it in items
    ) or "  (no items yet)"
    return (
        f"📄 *{inv.get('type','Invoice').upper()} #{inv.get('number','—')}*\n\n"
        f"🗓 Date: `{inv.get('date','—')}`   📅 Due: `{inv.get('due_date','—')}`\n"
        f"📐 Page: `{inv.get('page_size','A4')}`   💱 Currency: `{inv.get('currency','USD')}`\n\n"
        f"👤 *{inv.get('client_name','—')}*\n"
        f"📍 {inv.get('client_address','')}\n"
        f"📧 {inv.get('client_email','')}\n\n"
        f"📦 *Items:*\n{items_str}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Subtotal:  {fmt_cur(subtotal,sym)}\n"
        f"Discount ({disc}%): -{fmt_cur(d_amt,sym)}\n"
        f"Tax ({tax}%): +{fmt_cur(t_amt,sym)}\n"
        f"*TOTAL: {fmt_cur(total,sym)}*\n\n"
        f"💬 Notes: {inv.get('notes','—')}"
    )

def get_current_pro_price() -> tuple[int, dict | None]:
    """Returns (stars_to_charge, campaign_or_None)."""
    campaign = db.get_active_campaign()
    if campaign:
        disc     = campaign["discount_pct"]
        price    = round(PRO_BASE_PRICE * (1 - disc/100))
        return max(1, price), campaign
    return PRO_BASE_PRICE, None

def campaign_badge(campaign: dict) -> str:
    ends = campaign["ends_at"][:16].replace("T"," ")
    return (
        f"🔥 *LIMITED OFFER!* {campaign['discount_pct']}% OFF\n"
        f"Only *{campaign['stars_price']} ⭐ Stars* (was {PRO_BASE_PRICE})\n"
        f"Offer ends: `{ends} UTC`\n\n"
    )


# ─────────────────────────────────────────────────────────────────────────────
# START / MAIN MENU
# ─────────────────────────────────────────────────────────────────────────────

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.ensure_user(user.id, user.first_name, user.username or "")
    ctx.user_data.clear()

    plan       = db.get_user_plan(user.id)
    _, remaining = db.can_create_invoice(user.id)
    plan_badge = "✨ *Pro Plan*" if plan=="pro" else f"🆓 *Free Plan* ({FREE_LIMIT-remaining if remaining!=-1 else 0}/{FREE_LIMIT} used)"

    campaign = db.get_active_campaign()
    promo = ""
    if campaign and plan == "free":
        promo = f"\n\n{campaign_badge(campaign)}"

    text = (
        f"👋 Welcome, *{user.first_name}*!\n\n"
        f"🧾 *Invoice & Receipt Bot*\n"
        f"Create professional PDFs instantly.\n\n"
        f"Plan: {plan_badge}{promo}"
    )
    kb = main_menu_keyboard(user.id)
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=kb)
    else:
        await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
    return MAIN_MENU


async def main_menu_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    uid   = update.effective_user.id

    # ── New invoice / receipt ──────────────────────────────────────────────
    if data in ("new_invoice", "new_receipt"):
        allowed, remaining = db.can_create_invoice(uid)
        if not allowed:
            price, campaign = get_current_pro_price()
            promo = campaign_badge(campaign) if campaign else ""
            await query.edit_message_text(
                f"🚫 *Free limit reached!*\n\n"
                f"You've used all {FREE_LIMIT} free invoices.\n\n"
                f"{promo}"
                f"Upgrade to *Pro* for unlimited invoices & receipts.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"⭐ Upgrade — {price} Stars", callback_data="upgrade_pro")],
                    [InlineKeyboardButton("◀️ Back", callback_data="main_menu")],
                ]),
            )
            return MAIN_MENU

        ctx.user_data["invoice"] = {
            "type":      "Invoice" if data == "new_invoice" else "Receipt",
            "items":     [],
            "page_size": ctx.user_data.get("default_page_size", "A4"),
            "currency":  db.get_user_currency(uid),
        }
        company = db.get_company(uid)
        if not company:
            await query.edit_message_text(
                "🏢 First, set up your *company info*.\n\nCompany / business name:",
                parse_mode="Markdown",
            )
            return SETUP_COMPANY_NAME
        ctx.user_data["invoice"]["company"] = company
        return await _ask_client_name(query, ctx)

    # ── Company ────────────────────────────────────────────────────────────
    elif data == "my_company":
        company = db.get_company(uid)
        if company:
            text = (
                f"🏢 *Your Company*\n\n"
                f"*{company['name']}*\n"
                f"📍 {company.get('address','—')}\n"
                f"📧 {company.get('email','—')}\n"
                f"📞 {company.get('phone','—')}\n"
                f"🌐 {company.get('website','—')}\n"
                f"🪪 Tax ID: {company.get('tax_id','—')}"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Edit Company", callback_data="setup_company")],
                [InlineKeyboardButton("◀️ Main Menu",    callback_data="main_menu")],
            ])
        else:
            text = "No company profile yet. Let's set one up!"
            kb   = InlineKeyboardMarkup([
                [InlineKeyboardButton("🏢 Setup Company", callback_data="setup_company")],
                [InlineKeyboardButton("◀️ Main Menu",     callback_data="main_menu")],
            ])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=kb)
        return MAIN_MENU

    elif data == "setup_company":
        await query.edit_message_text("🏢 *Company Setup*\n\nCompany / business name:", parse_mode="Markdown")
        return SETUP_COMPANY_NAME

    # ── My Invoices ────────────────────────────────────────────────────────
    elif data == "my_invoices":
        invoices = db.get_invoices(uid)
        if not invoices:
            await query.edit_message_text(
                "📁 No documents yet.\nCreate your first invoice or receipt!",
                reply_markup=back_kb(),
            )
            return MAIN_MENU
        rows = []
        for inv in invoices[:15]:
            icon  = "🧾" if inv["type"]=="Invoice" else "📋"
            label = f"{icon} #{inv['number']} – {inv['client_name']} ({inv['date']})"
            rows.append([InlineKeyboardButton(label, callback_data=f"view_inv_{inv['id']}")])
        rows.append([InlineKeyboardButton("◀️ Main Menu", callback_data="main_menu")])
        await query.edit_message_text("📁 *Your recent documents:*", parse_mode="Markdown",
                                      reply_markup=InlineKeyboardMarkup(rows))
        return MAIN_MENU

    elif data.startswith("view_inv_"):
        inv_id = data.split("_")[-1]
        inv    = db.get_invoice(inv_id)
        if not inv:
            await query.edit_message_text("Invoice not found.", reply_markup=back_kb())
            return MAIN_MENU
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Download PDF", callback_data=f"dl_inv_{inv_id}")],
            [InlineKeyboardButton("🗑 Delete",        callback_data=f"del_inv_{inv_id}"),
             InlineKeyboardButton("◀️ Back",          callback_data="my_invoices")],
        ])
        await query.edit_message_text(invoice_summary(inv), parse_mode="Markdown", reply_markup=kb)
        return MAIN_MENU

    elif data.startswith("dl_inv_"):
        inv_id = data.split("_")[-1]
        inv    = db.get_invoice(inv_id)
        if not inv:
            await query.answer("Invoice not found", show_alert=True)
            return MAIN_MENU
        await query.answer("Generating PDF…")
        pdf_path = generate_invoice_pdf(inv)
        with open(pdf_path,"rb") as f:
            await ctx.bot.send_document(
                chat_id=update.effective_chat.id,
                document=f,
                filename=f"{inv['type']}_{inv['number']}.pdf",
                caption=f"📄 {inv['type']} #{inv['number']} — {inv['client_name']}",
            )
        os.remove(pdf_path)
        return MAIN_MENU

    elif data.startswith("del_inv_"):
        inv_id = data.split("_")[-1]
        db.delete_invoice(inv_id)
        await query.edit_message_text("🗑 Deleted.", reply_markup=back_kb())
        return MAIN_MENU

    # ── Currency ───────────────────────────────────────────────────────────
    elif data == "currency_settings":
        cur  = db.get_user_currency(uid)
        btns = [
            [InlineKeyboardButton(f"{'✅ ' if code==cur else ''}{sym} {code}",
                                  callback_data=f"setcur_{code}")
             for code, sym in list(CURRENCIES.items())[i:i+2]]
            for i in range(0, len(CURRENCIES), 2)
        ]
        btns.append([InlineKeyboardButton("◀️ Back", callback_data="main_menu")])
        await query.edit_message_text(
            f"💱 *Currency*\nCurrent: *{cur}*\nSelect default:",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns),
        )
        return MAIN_MENU

    elif data.startswith("setcur_"):
        db.set_user_currency(uid, data.split("_")[1])
        await query.answer(f"✅ Currency set to {data.split('_')[1]}", show_alert=True)
        return await start(update, ctx)

    # ── Page size ──────────────────────────────────────────────────────────
    elif data == "pagesize_settings":
        cur = ctx.user_data.get("default_page_size","A4")
        btns = [
            [InlineKeyboardButton(f"{'✅ ' if k==cur else ''}{v}",
                                  callback_data=f"setps_{k}")]
            for k, v in PAGE_SIZE_LABELS.items()
        ]
        btns.append([InlineKeyboardButton("◀️ Back", callback_data="main_menu")])
        await query.edit_message_text(
            "📐 *Default PDF Page Size*\nApplied to every new invoice:",
            parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns),
        )
        return MAIN_MENU

    elif data.startswith("setps_"):
        key = data.split("_",1)[1]
        ctx.user_data["default_page_size"] = key
        await query.answer(f"✅ Default page size: {key}", show_alert=True)
        return await start(update, ctx)

    # ── Upgrade ────────────────────────────────────────────────────────────
    elif data == "upgrade_pro":
        plan = db.get_user_plan(uid)
        if plan == "pro":
            await query.edit_message_text(
                "✨ You're already on *Pro*!\nEnjoy unlimited invoices & receipts.",
                parse_mode="Markdown", reply_markup=back_kb(),
            )
            return MAIN_MENU
        price, campaign = get_current_pro_price()
        promo = campaign_badge(campaign) if campaign else ""
        await query.edit_message_text(
            f"⭐ *Upgrade to Pro*\n\n"
            f"{promo}"
            f"✅ Unlimited invoices & receipts\n"
            f"✅ All page sizes\n"
            f"✅ Priority support\n\n"
            f"*Price: {price} Telegram Stars*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(f"⭐ Pay {price} Stars", callback_data="pay_stars")],
                [InlineKeyboardButton("◀️ Back", callback_data="main_menu")],
            ]),
        )
        return MAIN_MENU

    elif data == "pay_stars":
        plan = db.get_user_plan(uid)
        if plan == "pro":
            await query.answer("Already Pro!", show_alert=True)
            return MAIN_MENU
        price, campaign = get_current_pro_price()
        await ctx.bot.send_invoice(
            chat_id=update.effective_chat.id,
            title="Invoice Bot Pro",
            description=f"Unlimited invoices & receipts forever. ({price} Stars)",
            payload=f"pro_upgrade_{uid}_{campaign['id'] if campaign else 'none'}",
            currency="XTR",
            prices=[LabeledPrice("Invoice Bot Pro", price)],
        )
        return MAIN_MENU

    # ── Help ───────────────────────────────────────────────────────────────
    elif data == "help":
        await query.edit_message_text(
            "ℹ️ *How to use*\n\n"
            "1️⃣ Set up your *Company Profile* (once)\n"
            "2️⃣ Pick *New Invoice* or *New Receipt*\n"
            "3️⃣ Fill in client details\n"
            "4️⃣ Add line items\n"
            "5️⃣ Set tax, discount & notes\n"
            "6️⃣ Choose page size & currency\n"
            "7️⃣ Download beautiful *PDF* ✅\n\n"
            "📦 *Free plan:* 5 documents\n"
            "⭐ *Pro plan:* Unlimited (50 Stars)\n\n"
            "Commands:\n"
            "/start – Main menu\n"
            "/new   – Quick new invoice\n"
            "/cancel – Cancel current action",
            parse_mode="Markdown", reply_markup=back_kb(),
        )
        return MAIN_MENU

    elif data == "main_menu":
        return await start(update, ctx)

    # ── Admin ──────────────────────────────────────────────────────────────
    elif data == "admin_panel":
        if not _is_admin(uid):
            await query.answer("Not authorized.", show_alert=True)
            return MAIN_MENU
        return await show_admin_panel(query, ctx)

    elif data == "admin_stats":
        if not _is_admin(uid):
            return MAIN_MENU
        s = db.get_stats()
        c = db.get_pending_campaign()
        camp_str = ""
        if c:
            status = "🟢 ACTIVE" if db.get_active_campaign() else "🟡 PENDING/EXPIRED"
            camp_str = (
                f"\n\n🎟 *Current Campaign* ({status})\n"
                f"Price: {c['stars_price']} Stars  |  Discount: {c['discount_pct']}%\n"
                f"From: `{c['starts_at'][:16]}`\n"
                f"To:   `{c['ends_at'][:16]}`"
            )
        await query.edit_message_text(
            f"📊 *Bot Statistics*\n\n"
            f"👥 Total users:  {s['total_users']}\n"
            f"⭐ Pro users:    {s['pro_users']}\n"
            f"🆓 Free users:   {s['free_users']}\n"
            f"🧾 Total docs:   {s['total_invoices']}\n"
            f"💰 Stars earned: {s['total_stars']}"
            f"{camp_str}",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Admin Panel", callback_data="admin_panel")]
            ]),
        )
        return ADMIN_MENU

    elif data == "admin_new_campaign":
        if not _is_admin(uid):
            return MAIN_MENU
        await query.edit_message_text(
            "🎟 *Create Discount Campaign*\n\nStep 1/3 — How many ⭐ Stars should Pro cost?\n"
            f"(Base price is {PRO_BASE_PRICE} Stars)",
            parse_mode="Markdown",
        )
        ctx.user_data["campaign"] = {}
        return ADMIN_DISC_STARS

    elif data == "admin_cancel_campaign":
        if not _is_admin(uid):
            return MAIN_MENU
        cancelled = db.cancel_campaign()
        await query.edit_message_text(
            "✅ Campaign cancelled." if cancelled else "No active campaign to cancel.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Admin Panel", callback_data="admin_panel")]
            ]),
        )
        return ADMIN_MENU

    elif data == "admin_broadcast":
        if not _is_admin(uid):
            return MAIN_MENU
        campaign = db.get_active_campaign()
        hint = ""
        if campaign:
            hint = (
                f"\n\n💡 Active campaign: {campaign['discount_pct']}% off → {campaign['stars_price']} Stars "
                f"(ends {campaign['ends_at'][:10]})"
            )
        await query.edit_message_text(
            f"📢 *Broadcast to Free Users*{hint}\n\n"
            "Type your message below.\n"
            "You can use *bold*, _italic_, and emoji.\n\n"
            "Type /cancel to abort.",
            parse_mode="Markdown",
        )
        return ADMIN_BROADCAST_MSG

    return MAIN_MENU


async def show_admin_panel(query, ctx):
    campaign = db.get_pending_campaign()
    c_status = ""
    if campaign:
        active = bool(db.get_active_campaign())
        c_status = f"\n🎟 Campaign: {'🟢 Live' if active else '🟡 Scheduled'} — {campaign['discount_pct']}% off @ {campaign['stars_price']} ⭐"
    await query.edit_message_text(
        f"🔧 *Admin Panel*{c_status}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Stats",              callback_data="admin_stats")],
            [InlineKeyboardButton("🎟 New Discount Campaign", callback_data="admin_new_campaign")],
            [InlineKeyboardButton("🚫 Cancel Campaign",    callback_data="admin_cancel_campaign")],
            [InlineKeyboardButton("📢 Broadcast to Free Users", callback_data="admin_broadcast")],
            [InlineKeyboardButton("◀️ Main Menu",          callback_data="main_menu")],
        ]),
    )
    return ADMIN_MENU


# ─────────────────────────────────────────────────────────────────────────────
# ADMIN CAMPAIGN FLOW
# ─────────────────────────────────────────────────────────────────────────────

async def admin_disc_stars(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        stars = int(update.message.text.strip())
        assert 1 <= stars <= PRO_BASE_PRICE
    except (ValueError, AssertionError):
        await update.message.reply_text(f"⚠️ Enter a number between 1 and {PRO_BASE_PRICE}:")
        return ADMIN_DISC_STARS
    disc_pct = round((1 - stars / PRO_BASE_PRICE) * 100)
    ctx.user_data["campaign"]["stars_price"] = stars
    ctx.user_data["campaign"]["discount_pct"] = disc_pct
    await update.message.reply_text(
        f"✅ Price: *{stars} Stars* = {disc_pct}% discount\n\n"
        "Step 2/3 — How many *hours* should this offer last?\n(e.g. 24 for one day, 72 for 3 days)",
        parse_mode="Markdown",
    )
    return ADMIN_DISC_HOURS


async def admin_disc_hours(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        hours = float(update.message.text.strip())
        assert 0.5 <= hours <= 720
    except (ValueError, AssertionError):
        await update.message.reply_text("⚠️ Enter hours between 0.5 and 720:")
        return ADMIN_DISC_HOURS

    now      = datetime.now(timezone.utc)
    ends_at  = now + timedelta(hours=hours)
    starts   = now.isoformat()
    ends     = ends_at.isoformat()
    ctx.user_data["campaign"]["starts_at"] = starts
    ctx.user_data["campaign"]["ends_at"]   = ends
    c = ctx.user_data["campaign"]
    await update.message.reply_text(
        f"📋 *Campaign Preview*\n\n"
        f"⭐ Price: *{c['stars_price']} Stars* ({c['discount_pct']}% off)\n"
        f"🕐 Duration: {hours} hours\n"
        f"⏰ Ends: `{ends[:16]} UTC`\n\n"
        "Step 3/3 — Type a *broadcast message* to send to all free users,\n"
        "OR type `skip` to create the campaign silently.",
        parse_mode="Markdown",
    )
    return ADMIN_BROADCAST_MSG


async def admin_broadcast_msg(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid      = update.effective_user.id
    text_raw = update.message.text.strip()

    # Check if this came from campaign creation or standalone broadcast
    campaign_data = ctx.user_data.get("campaign")

    if campaign_data and campaign_data.get("starts_at"):
        # Create the campaign in DB
        c = campaign_data
        camp_id = db.create_campaign(
            stars_price  = c["stars_price"],
            discount_pct = c["discount_pct"],
            starts_at    = c["starts_at"],
            ends_at      = c["ends_at"],
            admin_id     = uid,
        )
        ctx.user_data.pop("campaign", None)
        await update.message.reply_text(
            f"✅ Campaign #{camp_id} created!\n"
            f"⭐ {c['stars_price']} Stars  |  {c['discount_pct']}% off\n"
            f"Ends: {c['ends_at'][:16]} UTC",
        )

    if text_raw.lower() == "skip":
        await update.message.reply_text("Campaign saved silently (no broadcast).",
                                        reply_markup=main_menu_keyboard(uid))
        return MAIN_MENU

    # Do broadcast
    free_users = db.get_all_free_users()
    sent = failed = 0
    status_msg = await update.message.reply_text(f"📢 Broadcasting to {len(free_users)} users…")

    for user in free_users:
        try:
            await update.get_bot().send_message(
                chat_id    = user["id"],
                text       = text_raw,
                parse_mode = "Markdown",
            )
            sent += 1
            await asyncio.sleep(0.05)  # rate-limit guard
        except Exception as e:
            logger.warning(f"Broadcast failed for {user['id']}: {e}")
            failed += 1

    await status_msg.edit_text(
        f"📢 *Broadcast complete!*\n\n"
        f"✅ Sent:   {sent}\n"
        f"❌ Failed: {failed}",
        parse_mode="Markdown",
    )
    await update.message.reply_text("Back to admin panel:", reply_markup=main_menu_keyboard(uid))
    return MAIN_MENU


# ─────────────────────────────────────────────────────────────────────────────
# COMPANY SETUP
# ─────────────────────────────────────────────────────────────────────────────

async def setup_company_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.setdefault("company",{})["name"] = update.message.text.strip()
    await update.message.reply_text("📍 Address (street, city, country):")
    return SETUP_COMPANY_ADDRESS

async def setup_company_address(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["company"]["address"] = update.message.text.strip()
    await update.message.reply_text("📧 Email:")
    return SETUP_COMPANY_EMAIL

async def setup_company_email(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["company"]["email"] = update.message.text.strip()
    await update.message.reply_text("📞 Phone:")
    return SETUP_COMPANY_PHONE

async def setup_company_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["company"]["phone"] = update.message.text.strip()
    await update.message.reply_text("🌐 Website (or 'skip'):")
    return SETUP_COMPANY_WEBSITE

async def setup_company_website(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    ctx.user_data["company"]["website"] = "" if v.lower()=="skip" else v
    await update.message.reply_text("🪪 Tax ID / VAT number (or 'skip'):")
    return SETUP_COMPANY_TAX_ID

async def setup_company_tax_id(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    ctx.user_data["company"]["tax_id"] = "" if v.lower()=="skip" else v
    db.save_company(update.effective_user.id, ctx.user_data["company"])
    await update.message.reply_text(
        f"✅ Company *{ctx.user_data['company']['name']}* saved!",
        parse_mode="Markdown",
    )
    if "invoice" in ctx.user_data:
        ctx.user_data["invoice"]["company"] = ctx.user_data["company"]
        await update.message.reply_text("👤 Client / customer name or company:")
        return INV_CLIENT_NAME
    await update.message.reply_text("What next?", reply_markup=main_menu_keyboard(update.effective_user.id))
    return MAIN_MENU


# ─────────────────────────────────────────────────────────────────────────────
# INVOICE CREATION FLOW
# ─────────────────────────────────────────────────────────────────────────────

async def _ask_client_name(query, ctx):
    await query.edit_message_text("👤 Client / customer name or company:")
    return INV_CLIENT_NAME

async def inv_client_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["invoice"]["client_name"] = update.message.text.strip()
    await update.message.reply_text("📍 Client address (or 'skip'):")
    return INV_CLIENT_ADDRESS

async def inv_client_address(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    ctx.user_data["invoice"]["client_address"] = "" if v.lower()=="skip" else v
    await update.message.reply_text("📧 Client email (or 'skip'):")
    return INV_CLIENT_EMAIL

async def inv_client_email(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    ctx.user_data["invoice"]["client_email"] = "" if v.lower()=="skip" else v
    await update.message.reply_text("📞 Client phone (or 'skip'):")
    return INV_CLIENT_PHONE

async def inv_client_phone(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    ctx.user_data["invoice"]["client_phone"] = "" if v.lower()=="skip" else v
    uid    = update.effective_user.id
    count  = db.get_user_invoice_count(uid) + 1
    prefix = "INV" if ctx.user_data["invoice"]["type"]=="Invoice" else "REC"
    auto   = f"{prefix}-{datetime.now().year}-{count:04d}"
    # Auto-set invoice number and date, skip asking
    ctx.user_data["invoice"]["number"] = auto
    ctx.user_data["invoice"]["date"]   = datetime.now().strftime("%Y-%m-%d")
    if ctx.user_data["invoice"]["type"] == "Receipt":
        ctx.user_data["invoice"]["due_date"] = ctx.user_data["invoice"]["date"]
        return await _ask_currency(update, ctx)
    await update.message.reply_text("📅 Payment due date (e.g. 2025-04-30, or 'skip' for same as issue date):")
    return INV_DUE_DATE

async def inv_due_date_or_skip(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # kept for compatibility — not used in new flow
    pass

async def inv_due_date(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    ctx.user_data["invoice"]["due_date"] = ctx.user_data["invoice"]["date"] if v.lower()=="skip" else v
    return await _ask_currency(update, ctx)

async def _ask_currency(update, ctx):
    cur  = ctx.user_data["invoice"].get("currency", db.get_user_currency(update.effective_user.id))
    btns = [
        [InlineKeyboardButton(f"{'✅ ' if code==cur else ''}{sym} {code}",
                              callback_data=f"cur_{code}")
         for code, sym in list(CURRENCIES.items())[i:i+2]]
        for i in range(0, len(CURRENCIES), 2)
    ]
    await update.message.reply_text(
        f"💱 Select currency (current: *{cur}*):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(btns),
    )
    return INV_CURRENCY

async def inv_currency_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    code = query.data.split("_",1)[1]
    ctx.user_data["invoice"]["currency"] = code
    # Page size picker
    cur_ps = ctx.user_data["invoice"].get("page_size","A4")
    btns = [
        [InlineKeyboardButton(f"{'✅ ' if k==cur_ps else ''}{v}", callback_data=f"ps_{k}")]
        for k, v in PAGE_SIZE_LABELS.items()
    ]
    await query.edit_message_text(
        f"📐 *PDF Page Size* (current: {cur_ps}):",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(btns),
    )
    return INV_PAGE_SIZE

async def inv_page_size_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_",1)[1]
    ctx.user_data["invoice"]["page_size"] = key
    cur_style = ctx.user_data["invoice"].get("pdf_style","classic")
    style_icons = {"classic":"🔵","dark":"⚫","minimal":"⚪","elegant":"🟢"}
    btns = [
        [InlineKeyboardButton(
            f"{'✅ ' if k==cur_style else ''}{style_icons.get(k,'')} {v}",
            callback_data=f"pdfstyle_{k}"
        )]
        for k,v in PDF_STYLES.items()
    ]
    await query.edit_message_text(
        f"📐 Page: *{key}*\n\n🎨 *Choose PDF style:*",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(btns),
    )
    return INV_TAX_RATE

async def inv_pdf_style_cb(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    key = query.data.split("_",1)[1]
    ctx.user_data["invoice"]["pdf_style"] = key
    await query.edit_message_text(
        f"🎨 Style: *{PDF_STYLES.get(key,key)}*\n\n💸 Tax rate % (e.g. 18, or 0):",
        parse_mode="Markdown",
    )
    return INV_TAX_RATE

async def inv_tax_rate(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        rate = float(update.message.text.strip().replace("%",""))
    except ValueError:
        rate = 0.0
    ctx.user_data["invoice"]["tax_rate"] = rate
    await update.message.reply_text("🏷 Discount % (e.g. 10, or 0):")
    return INV_DISCOUNT

async def inv_discount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        disc = float(update.message.text.strip().replace("%",""))
    except ValueError:
        disc = 0.0
    ctx.user_data["invoice"]["discount"] = disc
    await update.message.reply_text(
        "📦 *Add line items!*\n\nFirst item — product/service name:",
        parse_mode="Markdown",
    )
    ctx.user_data["current_item"] = {}
    return ITEM_NAME

async def item_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["current_item"]["name"] = update.message.text.strip()
    await update.message.reply_text("📦 Unit (e.g. pcs, kg, hr) — or 'skip':")
    return ITEM_UNIT

async def item_unit(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    ctx.user_data["current_item"]["unit"] = "pc" if v.lower()=="skip" else v
    await update.message.reply_text("🔢 Quantity:")
    return ITEM_QTY

async def item_qty(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        qty = float(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("⚠️ Enter a valid number:"); return ITEM_QTY
    ctx.user_data["current_item"]["qty"] = qty
    sym = CURRENCIES.get(ctx.user_data["invoice"].get("currency","USD"), "$")
    await update.message.reply_text(f"💵 Unit price ({sym}):")
    return ITEM_PRICE

async def item_price(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(update.message.text.strip().replace(",",""))
    except ValueError:
        await update.message.reply_text("⚠️ Enter a valid price:"); return ITEM_PRICE
    ctx.user_data["current_item"]["price"] = price
    item = ctx.user_data["current_item"]
    sym  = CURRENCIES.get(ctx.user_data["invoice"].get("currency","USD"), "$")
    sub  = item["qty"] * item["price"]
    await update.message.reply_text(
        f"✅ *{item['name']}* × {item['qty']} {item['unit']} @ {sym}{item['price']:.2f} = {sym}{sub:.2f}\n\nAdd this item?",
        parse_mode="Markdown", reply_markup=yes_no_kb(),
    )
    return CONFIRM_ITEM

async def confirm_item(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "yes":
        ctx.user_data["invoice"]["items"].append(dict(ctx.user_data["current_item"]))
    ctx.user_data["current_item"] = {}
    count = len(ctx.user_data["invoice"]["items"])
    sym   = CURRENCIES.get(ctx.user_data["invoice"].get("currency","USD"), "$")
    sub   = sum(i["qty"]*i["price"] for i in ctx.user_data["invoice"]["items"])
    await query.edit_message_text(
        f"📦 *{count} item(s)* — Subtotal: {sym}{sub:,.2f}\n\nWhat next?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Add Another Item",    callback_data="add_item")],
            [InlineKeyboardButton("📝 Add Notes & Finish", callback_data="finish_items")],
        ]),
    )
    return ADDING_ITEMS

async def adding_items_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "add_item":
        await query.edit_message_text("📦 Next item — name:")
        return ITEM_NAME
    await query.edit_message_text("💬 Notes / payment terms (or 'skip'):")
    return INV_NOTES

async def inv_notes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    v = update.message.text.strip()
    ctx.user_data["invoice"]["notes"] = "" if v.lower()=="skip" else v
    inv = ctx.user_data["invoice"]
    await update.message.reply_text(
        invoice_summary(inv),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Generate PDF", callback_data="generate_pdf"),
             InlineKeyboardButton("❌ Cancel",       callback_data="main_menu")],
        ]),
    )
    return REVIEW_INVOICE

async def generate_pdf_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("Generating PDF… ⏳")
    await query.edit_message_text("⏳ Creating your PDF, please wait…")

    uid = update.effective_user.id
    inv = ctx.user_data["invoice"]
    if "company" not in inv:
        inv["company"] = db.get_company(uid) or {}

    inv_id   = db.save_invoice(uid, inv)
    inv["id"] = inv_id
    pdf_path = generate_invoice_pdf(inv)

    ps_label = PAGE_SIZE_LABELS.get(inv.get("page_size","A4"), "A4")
    with open(pdf_path,"rb") as f:
        await ctx.bot.send_document(
            chat_id=update.effective_chat.id,
            document=f,
            filename=f"{inv['type']}_{inv['number']}.pdf",
            caption=(
                f"🎉 *{inv['type']} #{inv['number']}* ready!\n"
                f"Client: {inv['client_name']}\n"
                f"Page: {ps_label}"
            ),
            parse_mode="Markdown",
        )
    os.remove(pdf_path)
    ctx.user_data.clear()
    await ctx.bot.send_message(
        chat_id=update.effective_chat.id,
        text="What would you like to do next?",
        reply_markup=main_menu_keyboard(uid),
    )
    return MAIN_MENU


# ─────────────────────────────────────────────────────────────────────────────
# PAYMENTS (Telegram Stars)
# ─────────────────────────────────────────────────────────────────────────────

async def pre_checkout(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)

async def successful_payment(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    payment  = update.message.successful_payment
    payload  = payment.invoice_payload      # "pro_upgrade_{uid}_{camp_id|none}"
    uid      = update.effective_user.id
    stars    = payment.total_amount

    try:
        parts    = payload.split("_")
        camp_id  = None if parts[-1]=="none" else int(parts[-1])
    except Exception:
        camp_id = None

    db.upgrade_to_pro(uid)
    db.record_payment(uid, stars, camp_id)

    await update.message.reply_text(
        f"🎉 *Welcome to Pro!*\n\n"
        f"You paid *{stars} ⭐ Stars*.\n"
        "Enjoy *unlimited* invoices & receipts!\n\n"
        "Use /start to get going.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard(uid),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CANCEL
# ─────────────────────────────────────────────────────────────────────────────

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text(
        "❌ Cancelled.", reply_markup=main_menu_keyboard(update.effective_user.id)
    )
    return MAIN_MENU


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    import os
    BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN environment variable is not set!")
    app = Application.builder().token(BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CommandHandler("new",   start),
        ],
        states={
            MAIN_MENU: [CallbackQueryHandler(main_menu_handler)],

            SETUP_COMPANY_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_company_name)],
            SETUP_COMPANY_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_company_address)],
            SETUP_COMPANY_EMAIL:   [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_company_email)],
            SETUP_COMPANY_PHONE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_company_phone)],
            SETUP_COMPANY_WEBSITE: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_company_website)],
            SETUP_COMPANY_TAX_ID:  [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_company_tax_id)],

            INV_CLIENT_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_client_name)],
            INV_CLIENT_ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_client_address)],
            INV_CLIENT_EMAIL:   [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_client_email)],
            INV_CLIENT_PHONE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_client_phone)],
            INV_DUE_DATE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_due_date)],
            INV_CURRENCY:       [CallbackQueryHandler(inv_currency_cb,    pattern="^cur_")],
            INV_PAGE_SIZE:      [CallbackQueryHandler(inv_page_size_cb,   pattern="^ps_"),
                                CallbackQueryHandler(inv_pdf_style_cb,  pattern="^pdfstyle_")],
            INV_TAX_RATE:       [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_tax_rate),
                                CallbackQueryHandler(inv_pdf_style_cb,  pattern="^pdfstyle_")],
            INV_DISCOUNT:       [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_discount)],

            ITEM_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, item_name)],
            ITEM_UNIT:     [MessageHandler(filters.TEXT & ~filters.COMMAND, item_unit)],
            ITEM_QTY:      [MessageHandler(filters.TEXT & ~filters.COMMAND, item_qty)],
            ITEM_PRICE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, item_price)],
            CONFIRM_ITEM:  [CallbackQueryHandler(confirm_item,          pattern="^(yes|no)$")],
            ADDING_ITEMS:  [CallbackQueryHandler(adding_items_handler,  pattern="^(add_item|finish_items)$")],

            INV_NOTES:      [MessageHandler(filters.TEXT & ~filters.COMMAND, inv_notes)],
            REVIEW_INVOICE: [
                CallbackQueryHandler(generate_pdf_handler, pattern="^generate_pdf$"),
                CallbackQueryHandler(main_menu_handler,    pattern="^main_menu$"),
            ],

            ADMIN_MENU: [CallbackQueryHandler(main_menu_handler)],
            ADMIN_DISC_STARS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_disc_stars)],
            ADMIN_DISC_HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_disc_hours)],
            ADMIN_BROADCAST_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_msg)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(PreCheckoutQueryHandler(pre_checkout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, successful_payment))

    logger.info("🚀 Invoice Bot running…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
