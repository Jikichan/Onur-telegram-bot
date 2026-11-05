import os, sqlite3, csv, io, threading
from datetime import datetime, date
from zoneinfo import ZoneInfo
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.environ["BOT_TOKEN"]
TZ = ZoneInfo("Asia/Tashkent")
ADMIN_IDS = {int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()}
FATHER_IDS = {int(x.strip()) for x in os.getenv("FATHER_IDS", "").split(",") if x.strip()}
DB_PATH = os.getenv("DB_PATH", "onur.db")

app_web = Flask(__name__)
@app_web.get("/")
def health():
    return "ONUR bot is running", 200

def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER NOT NULL,
            worker_name TEXT NOT NULL,
            product_type TEXT NOT NULL,
            product_name TEXT NOT NULL,
            size TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS workers (
            telegram_id INTEGER PRIMARY KEY,
            worker_name TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1
        )""")

def now():
    return datetime.now(TZ)

def main_menu(uid):
    rows = [[ "➕ Hisob kiritish", "📋 Bugungi hisobim" ],
            [ "📅 Oldingi kunlar" ]]
    if uid in ADMIN_IDS:
        rows += [[ "📊 Bugungi ishlab chiqarish", "👷 Ishchilar hisoboti" ],
                 [ "📆 Oylik hisobot", "📥 Excel hisobot" ],
                 [ "👥 Ishchilar ro‘yxati" ]]
    elif uid in FATHER_IDS:
        rows += [[ "📊 Bugungi ishlab chiqarish", "📆 Oylik hisobot" ]]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)

def is_admin(uid): return uid in ADMIN_IDS
def is_reader(uid): return uid in FATHER_IDS or uid in ADMIN_IDS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    context.user_data.clear()
    with db() as c:
        row = c.execute("SELECT worker_name FROM workers WHERE telegram_id=? AND active=1", (uid,)).fetchone()
    if not row and not is_reader(uid):
        context.user_data["state"] = "register"
        await update.message.reply_text(
            "Assalomu alaykum! ONUR botiga xush kelibsiz.\nIsm-familiyangizni yozing. Rahbar tasdiqlagach hisob kiritishingiz mumkin.",
            reply_markup=ReplyKeyboardRemove())
        return
    name = row["worker_name"] if row else ("Rahbar" if is_admin(uid) else "Hisobot")
    await update.message.reply_text(f"Xush kelibsiz, {name}!\nONUR ishlab chiqarish hisobi.",
                                    reply_markup=main_menu(uid))

async def add_worker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("Bu buyruq faqat rahbar uchun.")
        return
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Foydalanish: /tasdiq TELEGRAM_ID Ism Familiya")
        return
    try: target = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Telegram ID raqam bo‘lishi kerak."); return
    name = " ".join(context.args[1:])
    with db() as c:
        c.execute("INSERT INTO workers(telegram_id,worker_name,active) VALUES(?,?,1) ON CONFLICT(telegram_id) DO UPDATE SET worker_name=excluded.worker_name,active=1", (target,name))
    await update.message.reply_text(f"{name} ONUR ishchisi sifatida tasdiqlandi.")

async def pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Bu buyruq faqat rahbar uchun."); return
    with db() as c:
        rows = c.execute("SELECT telegram_id,worker_name FROM workers ORDER BY worker_name").fetchall()
    if not rows:
        await update.message.reply_text("Hozircha tasdiqlangan ishchilar yo‘q."); return
    msg = "Ishchilar:\n" + "\n".join(f"{r['worker_name']} — ID: {r['telegram_id']}" for r in rows)
    await update.message.reply_text(msg)

async def send_report(update, period="today"):
    uid = update.effective_user.id
    if period == "today":
        start = now().date().isoformat()
        with db() as c:
            rows = c.execute("SELECT worker_name,product_type,product_name,size,SUM(quantity) q FROM entries WHERE substr(created_at,1,10)=? GROUP BY worker_name,product_type,product_name,size ORDER BY worker_name", (start,)).fetchall()
        title = f"Bugungi hisobot ({start})"
    else:
        month = now().strftime("%Y-%m")
        with db() as c:
            rows = c.execute("SELECT worker_name,product_type,product_name,size,SUM(quantity) q FROM entries WHERE substr(created_at,1,7)=? GROUP BY worker_name,product_type,product_name,size ORDER BY worker_name", (month,)).fetchall()
        title = f"Oylik hisobot ({month})"
    if not rows:
        await update.message.reply_text(title + "\nHozircha ma’lumot yo‘q.", reply_markup=main_menu(uid)); return
    total = sum(r["q"] for r in rows)
    lines = [title, f"Jami: {total} dona", ""]
    for r in rows:
        lines.append(f"{r['worker_name']}: {r['product_type']} / {r['product_name']} / {r['size']} — {r['q']} dona")
    await update.message.reply_text("\n".join(lines), reply_markup=main_menu(uid))

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    uid = update.effective_user.id
    text = (msg.text or "").strip()
    state = context.user_data.get("state")

    if state == "register":
        if len(text) < 2:
            await msg.reply_text("Ism-familiyangizni to‘liqroq yozing."); return
        with db() as c:
            c.execute("INSERT OR REPLACE INTO workers(telegram_id,worker_name,active) VALUES(?,?,0)", (uid,text))
    # menu actions
    if text == "➕ Hisob kiritish":
        with db() as c:
            w = c.execute("SELECT worker_name,active FROM workers WHERE telegram_id=?", (uid,)).fetchone()
        if not w or not w["active"]:
            await msg.reply_text("Hisob kiritish uchun rahbar tasdig‘i kerak. Telegram ID’ingiz: " + str(uid)); return
        context.user_data.clear(); context.user_data["state"]="type"
        await msg.reply_text("Mahsulot turini tanlang:", reply_markup=ReplyKeyboardMarkup([["Qozon","Tova"],["Boshqa mahsulot"]],resize_keyboard=True)); return
    if state == "type":
        if text not in ["Qozon","Tova","Boshqa mahsulot"]:
            await msg.reply_text("Tugmalardan birini tanlang."); return
        context.user_data["product_type"]=text; context.user_data["state"]="name"
        await msg.reply_text("Mahsulot nomini yozing (masalan: Kukmara, emal, alyumin):"); return
    if state == "name":
        context.user_data["product_name"]=text; context.user_data["state"]="size"
        await msg.reply_text("O‘lchamini yozing (masalan: 24 sm, 28 sm yoki —):"); return
    if state == "size":
        context.user_data["size"]=text; context.user_data["state"]="qty"
        await msg.reply_text("Nechta dona ishlab chiqarildi? Faqat son kiriting:"); return
    if state == "qty":
        try: q=int(text); assert q>0
        except Exception:
            await msg.reply_text("Soni 1 yoki undan katta butun raqam bo‘lishi kerak."); return
        context.user_data["quantity"]=q; context.user_data["state"]="note"
        await msg.reply_text("Izoh yozing yoki izoh bo‘lmasa — yuboring:"); return
    if state == "note":
        with db() as c:
            w=c.execute("SELECT worker_name FROM workers WHERE telegram_id=? AND active=1",(uid,)).fetchone()
            if not w:
                await msg.reply_text("Ishchi tasdiqlanmagan. Rahbar bilan bog‘laning."); return
            c.execute("INSERT INTO entries(telegram_id,worker_name,product_type,product_name,size,quantity,note,created_at) VALUES(?,?,?,?,?,?,?,?)",
                (uid,w["worker_name"],context.user_data["product_type"],context.user_data["product_name"],context.user_data["size"],context.user_data["quantity"],"" if text=="—" else text,now().isoformat(timespec="seconds")))
        summary=f"Hisob saqlandi:\n{context.user_data['product_type']} — {context.user_data['product_name']}\nO‘lcham: {context.user_data['size']}\nSoni: {context.user_data['quantity']} dona"
        context.user_data.clear()
        await msg.reply_text(summary,reply_markup=main_menu(uid)); return
    if text == "📋 Bugungi hisobim":
        with db() as c:
            rows=c.execute("SELECT product_type,product_name,size,SUM(quantity) q FROM entries WHERE telegram_id=? AND substr(created_at,1,10)=? GROUP BY product_type,product_name,size",(uid,now().date().isoformat())).fetchall()
        await msg.reply_text("Bugungi hisobingiz:\n" + ("\n".join(f"{r['product_type']} {r['product_name']} {r['size']}: {r['q']} dona" for r in rows) if rows else "Hozircha hisob kiritilmagan."),reply_markup=main_menu(uid)); return
    if text == "📅 Oldingi kunlar":
        with db() as c:
            rows=c.execute("SELECT substr(created_at,1,10) d,SUM(quantity) q FROM entries WHERE telegram_id=? GROUP BY d ORDER BY d DESC LIMIT 10",(uid,)).fetchall()
        await msg.reply_text("Oxirgi hisoblar:\n"+("\n".join(f"{r['d']}: {r['q']} dona" for r in rows) if rows else "Ma’lumot yo‘q."),reply_markup=main_menu(uid)); return
    if text == "📊 Bugungi ishlab chiqarish":
        if not is_reader(uid): await msg.reply_text("Ruxsat yo‘q."); return
        await send_report(update,"today"); return
    if text == "📆 Oylik hisobot":
        if not is_reader(uid): await msg.reply_text("Ruxsat yo‘q."); return
        await send_report(update,"month"); return
    if text == "👷 Ishchilar hisoboti":
        if not is_admin(uid): await msg.reply_text("Ruxsat yo‘q."); return
        await send_report(update,"month"); return
    if text == "👥 Ishchilar ro‘yxati":
        if not is_admin(uid): await msg.reply_text("Ruxsat yo‘q."); return
        await pending(update,context); return
    if text == "📥 Excel hisobot":
        if not is_admin(uid): await msg.reply_text("Ruxsat yo‘q."); return
        with db() as c: rows=c.execute("SELECT created_at,worker_name,product_type,product_name,size,quantity,note FROM entries ORDER BY created_at DESC").fetchall()
        s=io.StringIO(); w=csv.writer(s); w.writerow(["Sana","Ishchi","Turi","Mahsulot","O‘lcham","Soni","Izoh"])
        for r in rows: w.writerow(list(r))
        bio=io.BytesIO(("\ufeff"+s.getvalue()).encode("utf-8")); bio.name="ONUR_hisobot.csv"
        await msg.reply_document(bio,caption="ONUR ishlab chiqarish hisoboti"); return
    if state == "register":
        await msg.reply_text(f"Rahmat! Telegram ID’ingiz: {uid}\nRahbar shu ID orqali tasdiqlaydi: /tasdiq {uid} {text}")
        return
    await msg.reply_text("Menyudan kerakli bo‘limni tanlang yoki /start bosing.",reply_markup=main_menu(uid))

def run_web():
    port=int(os.getenv("PORT","10000"))
    app_web.run(host="0.0.0.0",port=port)

def main():
    init_db()
    threading.Thread(target=run_web,daemon=True).start()
    application=Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start",start))
    application.add_handler(CommandHandler("tasdiq",add_worker))
    application.add_handler(CommandHandler("ishchilar",pending))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,handle))
    application.run_polling()

if __name__ == "__main__":
    main()
