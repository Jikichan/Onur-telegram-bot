ONUR TELEGRAM BOT — SINOV

Fayllar:
- bot.py: bot dasturi
- requirements.txt: kerakli kutubxonalar
- render.yaml: Render sozlamalari

Render Environment Variables:
BOT_TOKEN = BotFather bergan token (maxfiy)
ADMIN_IDS = rahbar Telegram ID raqami
FATHER_IDS = dada uchun Telegram ID raqami

Bir nechta ID bo‘lsa vergul bilan yozing.
Masalan: 123456789,987654321

Ishchilar:
1. Botga /start yuboradi.
2. Ism-familiyasini yozadi.
3. Bot Telegram ID raqamini chiqaradi.
4. Rahbar botga /tasdiq TELEGRAM_ID Ism Familiya deb yuborib tasdiqlaydi.

Rahbar buyruqlari:
/tasdiq TELEGRAM_ID Ism Familiya
/ishchilar

Eslatma:
Bu birinchi sinov versiyasi. Render bepul xizmatida fayl bazasi qayta deploy yoki xizmat qayta yaratilganda yo‘qolishi mumkin. Haqiqiy ishga tushirishdan oldin doimiy disk yoki PostgreSQL bazasiga o‘tkazing.
Tokenni hech kimga yubormang. Uni faqat Render Environment Variables ichiga kiriting.
