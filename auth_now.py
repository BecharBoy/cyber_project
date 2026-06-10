"""
Authenticate using QR code — no phone code needed.

    /usr/local/bin/python3.14 auth_now.py

Steps:
  1. Run this script
  2. A QR code appears in the terminal
  3. Open Telegram on your phone
     → Settings → Devices → Link Desktop Device
  4. Scan the QR code
  5. Done — session saved permanently
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import qrcode
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telegram_api import config

SESSION = os.path.join(os.path.dirname(os.path.abspath(__file__)), "telegram_session")


async def main():
    client = TelegramClient(SESSION, config.API_ID, config.API_HASH)
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        print(f"\n✓ Already signed in as: {me.first_name}  (phone: {me.phone})")
        print("  Run the dashboard:  /usr/local/bin/python3.14 run_dashboard.py\n")
        await client.disconnect()
        return

    print("\nGenerating QR code...\n")

    qr_login = await client.qr_login()

    def print_qr(url):
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)

    print_qr(qr_login.url)

    print("""
╔═══════════════════════════════════════════════════════╗
║  SCAN THIS QR CODE WITH TELEGRAM ON YOUR PHONE        ║
║                                                       ║
║  Telegram → Settings → Devices → Link Desktop Device  ║
║  (or tap the QR icon on the login screen)             ║
║                                                       ║
║  Waiting for you to scan... (30 sec timeout)          ║
╚═══════════════════════════════════════════════════════╝
""")

    try:
        await qr_login.wait(30)
    except asyncio.TimeoutError:
        # QR expired — regenerate once
        print("QR expired, generating new one...\n")
        await qr_login.recreate()
        print_qr(qr_login.url)
        print("Waiting again (30 sec)...\n")
        try:
            await qr_login.wait(30)
        except asyncio.TimeoutError:
            print("Timed out. Run the script again and scan faster.\n")
            await client.disconnect()
            sys.exit(1)
    except SessionPasswordNeededError:
        pw = input("Two-step verification is ON. Enter your cloud password: ").strip()
        await client.sign_in(password=pw)

    me = await client.get_me()
    print(f"\n✓ Signed in as: {me.first_name}  (id: {me.id})")
    print("  Session saved. Run the dashboard:\n")
    print("      /usr/local/bin/python3.14 run_dashboard.py\n")
    await client.disconnect()


asyncio.run(main())
