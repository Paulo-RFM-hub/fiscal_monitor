from flask import Flask, render_template_string, request, redirect, url_for
from datetime import datetime

from .storage import MonitorStorage
from .fetcher import FetchError, PageFetcher
from .utils import compute_hash


def create_app():
    app = Flask(__name__)
    app.secret_key = "dev-secret"

    @app.route("/")
    def index():
        storage = MonitorStorage()
        monitors = storage.list_monitors()
        return render_template_string(INDEX_TEMPLATE, monitors=monitors)

    @app.route("/add", methods=["POST"])
    def add():
        name = request.form.get("name")
        url = request.form.get("url")
        selector = request.form.get("selector") or None
        if not name or not url:
            return redirect(url_for("index"))
        storage = MonitorStorage()
        storage.add_monitor(name, url, selector)
        return redirect(url_for("index"))

    def _check_monitor(storage, monitor):
        fetcher = PageFetcher(timeout=30)
        try:
            content = fetcher.fetch(monitor["url"], monitor.get("selector"))
            current_hash = compute_hash(content)
            if not monitor["last_hash"]:
                status = "ok"
                summary = "Primeira verificação ou base inicializada."
            elif current_hash != monitor["last_hash"]:
                status = "updated"
                summary = "Conteúdo alterado em relação à última versão salva."
            else:
                status = "ok"
                summary = "Sem alteração detectada."
            error = None
        except FetchError as exc:
            status = "error"
            error = str(exc)
            summary = "Falha ao baixar a página."
            current_hash = monitor.get("last_hash")

        storage.update_check_result(monitor["id"], status, current_hash, error)
        return {"status": status, "summary": summary, "error": error}

    @app.route("/check/<int:monitor_id>", methods=["POST"])
    def check(monitor_id):
        storage = MonitorStorage()
        monitor = storage.get_monitor(monitor_id)
        if not monitor:
            return redirect(url_for("index"))
        result = _check_monitor(storage, monitor)
        return render_template_string(CHECK_RESULT_TEMPLATE, monitor=monitor, result=result)

    @app.route("/check_all", methods=["POST"])
    def check_all():
        storage = MonitorStorage()
        monitors = storage.list_monitors()
        updated = []
        for m in monitors:
            res = _check_monitor(storage, m)
            if res.get("status") == "updated":
                updated.append((m, res))
        return render_template_string(CHECK_ALL_TEMPLATE, results=updated)

    @app.route("/delete/<int:monitor_id>", methods=["POST"])
    def delete(monitor_id):
      storage = MonitorStorage()
      storage.delete_monitor(monitor_id)
      return redirect(url_for("index"))

    @app.route("/history/<int:monitor_id>")
    def history(monitor_id):
        storage = MonitorStorage()
        monitor = storage.get_monitor(monitor_id)
        if not monitor:
            return redirect(url_for("index"))
        history = storage.get_history(monitor_id, limit=100)
        return render_template_string(HISTORY_TEMPLATE, monitor=monitor, history=history)

    return app


def run_server(host="127.0.0.1", port=5000):
    app = create_app()
    app.run(host=host, port=port)


INDEX_TEMPLATE = """
<!doctype html>
<title>Fiscal Monitor</title>
<h1>Monitores</h1>
<form action="/add" method="post">
  <input name="name" placeholder="Nome" required>
  <input name="url" placeholder="URL" required size="60">
  <input name="selector" placeholder="Seletor CSS (opcional)">
  <button type="submit">Adicionar</button>
</form>
<form action="/check_all" method="post" style="margin-top:10px;">
  <button type="submit">Verificar todos</button>
</form>
<table border=1 cellpadding=6 cellspacing=0 style="margin-top:10px;">
  <tr><th>ID</th><th>Nome</th><th>URL</th><th>Selector</th><th>Último Check</th><th>Status</th><th>Ações</th></tr>
  {% for m in monitors %}
  <tr>
    <td>{{m.id}}</td>
    <td>{{m.name}}</td>
    <td><a href="{{m.url}}" target="_blank">link</a></td>
    <td>{{m.selector or '-'}}</td>
    <td>{{m.last_checked or '-'}}</td>
    <td>{{m.last_status or 'pending'}}</td>
    <td>
      <form action="/check/{{m.id}}" method="post" style="display:inline;"><button type="submit">Verificar</button></form>
      <a href="/history/{{m.id}}">Histórico</a>
      <form action="/delete/{{m.id}}" method="post" style="display:inline;margin-left:6px;"><button type="submit" onclick="return confirm('Excluir monitor?')">Excluir</button></form>
    </td>
  </tr>
  {% endfor %}
</table>
"""


CHECK_RESULT_TEMPLATE = """
<!doctype html>
<title>Resultado da verificação</title>
<h1>Resultado para {{monitor.name}}</h1>
<p>Status: {{result.status}}</p>
<p>Resumo: {{result.summary}}</p>
<p>Erro: {{result.error or '-'}}</p>
<p><a href="/">Voltar</a> | <a href="/history/{{monitor.id}}">Ver histórico</a></p>
"""


CHECK_ALL_TEMPLATE = """
<!doctype html>
<title>Resultados</title>
<h1>Alterações detectadas</h1>
{% if results %}
<ul>
  {% for m, r in results %}
    <li>{{m.name}} ({{m.url}}) → {{r.status}} - {{r.summary}}</li>
  {% endfor %}
</ul>
{% else %}
<p>Nenhuma alteração detectada.</p>
{% endif %}
<p><a href="/">Voltar</a></p>
"""


HISTORY_TEMPLATE = """
<!doctype html>
<title>Histórico</title>
<h1>Histórico: {{monitor.name}}</h1>
<table border=1 cellpadding=6 cellspacing=0>
  <tr><th>Data</th><th>Status</th><th>Hash</th><th>Erro</th></tr>
  {% for row in history %}
  <tr>
    <td>{{row.checked_at}}</td>
    <td>{{row.status}}</td>
    <td>{{row.hash or '-'}}</td>
    <td>{{row.error or '-'}}</td>
  </tr>
  {% endfor %}
</table>
<p><a href="/">Voltar</a></p>
"""
