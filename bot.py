from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

EMAIL_FR_RE = re.compile(
    r"[a-zA-Z0-9][a-zA-Z0-9._+\-]*@[a-zA-Z0-9][a-zA-Z0-9.\-]*\.fr\b",
    re.IGNORECASE,
)

MAX_FILE_MB = 20


def line_has_fr_email(line: str) -> bool:
    return bool(EMAIL_FR_RE.search(line))


def extract_fr_lines(text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if line_has_fr_email(s) and s not in seen:
            seen.add(s)
            out.append(s)
    return out


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.document:
        return

    doc = update.message.document
    if doc.file_size and doc.file_size > MAX_FILE_MB * 1024 * 1024:
        await update.message.reply_text(f"Fichier trop lourd (max {MAX_FILE_MB} Mo).")
        return

    await update.message.reply_text("Fichier reçu, extraction en cours…")

    tg_file = await context.bot.get_file(doc.file_id)
    suffix = Path(doc.file_name or "input.txt").suffix or ".txt"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_in:
        in_path = Path(tmp_in.name)

    try:
        await tg_file.download_to_drive(str(in_path))
        try:
            content = in_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = in_path.read_text(encoding="latin-1")

        lines = extract_fr_lines(content)
        if not lines:
            await update.message.reply_text("Aucune ligne valide (email finissant par .fr).")
            return

        stem = Path(doc.file_name or "data").stem
        out_name = f"{stem}_emails_fr.txt"
        out_body = "\n".join(lines) + "\n"

        with tempfile.NamedTemporaryFile(
            mode="w", delete=False, suffix=".txt", encoding="utf-8"
        ) as tmp_out:
            out_path = Path(tmp_out.name)
            tmp_out.write(out_body)

        try:
            with out_path.open("rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=out_name,
                    caption=f"{len(lines)} ligne(s) avec email .fr",
                )
        finally:
            out_path.unlink(missing_ok=True)

    except Exception as exc:
        await update.message.reply_text(f"Erreur : {exc}")
    finally:
        in_path.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Bot Telegram extracteur emails .fr")
    ap.add_argument("--token", help="Token du bot (sinon variable TELEGRAM_BOT_TOKEN)")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    token = (args.token or os.environ.get("TELEGRAM_BOT_TOKEN", "8941153819:AAHNYz0Zy6j5zcqH3wB2nGSV4AJQp3DHQmo")).strip()
    if not token:
        print(
            "Token manquant.\n"
            "  set TELEGRAM_BOT_TOKEN=votre_token\n"
            "  python bot.py",
            file=sys.stderr,
        )
        raise SystemExit(1)

    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("Bot actif — envoie un fichier sur Telegram. Ctrl+C pour arrêter.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
