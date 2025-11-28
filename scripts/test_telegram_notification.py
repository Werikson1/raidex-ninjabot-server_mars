"""
Send a manual Telegram notification to verify bot credentials.
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is on sys.path when running as a script
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from modules import config  # noqa: E402
from modules.notifications import TelegramNotifier  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Enviar notificacao de teste via Telegram.")
    parser.add_argument("--chat-id", help="Chat ID para envio (sobrescreve config.json).")
    parser.add_argument(
        "--message",
        default="Teste de notificacao do Ogame XBot - SUCESSO!!!.",
        help="Texto a ser enviado.",
    )
    args = parser.parse_args()

    chat_id = args.chat_id or config.TELEGRAM_CHAT_ID
    if not chat_id:
        print("Chat ID ausente. Defina TELEGRAM_CHAT_ID no config.json ou use --chat-id.")
        sys.exit(1)

    notifier = TelegramNotifier(enabled=True)
    ok = notifier.send(args.message, chat_id=chat_id)

    if ok:
        print(f"Mensagem enviada para {chat_id}.")
    else:
        print("Falha ao enviar a mensagem. Verifique token, chat id e se o bot recebeu /start.")


if __name__ == "__main__":
    main()
