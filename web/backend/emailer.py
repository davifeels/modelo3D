"""Envio de e-mails com log obrigatório em email_logs.

Com SMTP_HOST definido envia de verdade (SMTP_PORT/SMTP_USER/SMTP_PASS/
SMTP_FROM, STARTTLS quando SMTP_TLS=1). Sem SMTP_HOST o envio é SIMULADO:
nada sai da máquina, mas o log registra status 'simulado' — o fluxo do painel
(botão "Enviar acesso") funciona de ponta a ponta em dev e homologação.

APP_URL é o link do sistema incluído no e-mail de credenciais.
"""
import os
import smtplib
from email.message import EmailMessage

from sqlalchemy.orm import Session

from models import EmailLog

APP_URL = os.environ.get("APP_URL", "http://localhost:5173")


def _smtp_configured() -> bool:
    return bool(os.environ.get("SMTP_HOST"))


def _send_smtp(to: str, subject: str, body: str):
    msg = EmailMessage()
    msg["From"] = os.environ.get("SMTP_FROM", "no-reply@zefirosplit.local")
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port, timeout=15) as s:
        if os.environ.get("SMTP_TLS", "1") == "1":
            s.starttls()
        user = os.environ.get("SMTP_USER")
        if user:
            s.login(user, os.environ.get("SMTP_PASS", ""))
        s.send_message(msg)


def send_email(db: Session, *, to: str, subject: str, body: str,
               user_id: str | None = None) -> str:
    """Envia (ou simula) e SEMPRE grava em email_logs. Retorna o status."""
    if _smtp_configured():
        try:
            _send_smtp(to, subject, body)
            status = "enviado"
        except Exception:
            status = "falhou"
    else:
        status = "simulado"
    db.add(EmailLog(user_id=user_id, destinatario=to, assunto=subject, status=status))
    db.commit()
    return status


def reset_email(*, nome: str | None, link: str) -> tuple[str, str]:
    """(assunto, corpo) do e-mail de recuperação de senha (link com token)."""
    saudacao = f"Olá, {nome}!" if nome else "Olá!"
    subject = "Redefinição de senha — ZefiroSplit"
    body = (
        f"{saudacao}\n\n"
        f"Recebemos um pedido para redefinir a senha da sua conta ZefiroSplit.\n"
        f"Clique no link abaixo para criar uma nova senha (válido por 1 hora):\n\n"
        f"  {link}\n\n"
        f"Se você não pediu isso, ignore este e-mail — sua senha atual continua "
        f"valendo.\n\n"
        f"— Equipe ZefiroSplit"
    )
    return subject, body


def credentials_email(*, nome: str | None, email: str, senha: str,
                      codigo: str) -> tuple[str, str]:
    """(assunto, corpo) do e-mail de acesso enviado pelo painel."""
    saudacao = f"Olá, {nome}!" if nome else "Olá!"
    subject = "Seu acesso ao ZefiroSplit"
    body = (
        f"{saudacao}\n\n"
        f"Seu acesso ao ZefiroSplit está pronto. Use as credenciais abaixo:\n\n"
        f"  Login:            {email}\n"
        f"  Senha:            {senha}\n"
        f"  Código de acesso: {codigo}\n\n"
        f"Acesse o sistema em: {APP_URL}/login\n\n"
        f"Recomendamos alterar a senha após o primeiro acesso.\n\n"
        f"— Equipe ZefiroSplit"
    )
    return subject, body
