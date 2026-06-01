import json
import requests


class NotificationError(Exception):
    pass


class TeamsNotifier:
    def __init__(self, webhook_url):
        self.webhook_url = webhook_url

    def send_change(self, monitor, status, checked_at, summary=None, error=None):
        title = "Alteração detectada" if status == "updated" else "Verificação concluída"
        details = [
            f"**Nome:** {monitor['name']}",
            f"**URL:** {monitor['url']}",
            f"**Status:** {status}",
            f"**Data:** {checked_at}",
        ]
        if summary:
            details.append(f"**Resumo:** {summary}")
        if error:
            details.append(f"**Erro:** {error}")

        payload = {
            "@type": "MessageCard",
            "@context": "https://schema.org/extensions",
            "summary": title,
            "themeColor": "0078D7",
            "title": title,
            "text": "\n\n".join(details),
        }

        response = requests.post(self.webhook_url, json=payload, timeout=10)
        try:
            response.raise_for_status()
        except requests.RequestException as exc:
            raise NotificationError(f"Falha ao enviar Teams: {exc}") from exc
