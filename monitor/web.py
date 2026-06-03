from flask import Flask, render_template_string, request, redirect, url_for
from datetime import datetime
from urllib.parse import urlparse

from .storage import MonitorStorage
from .fetcher import FetchError, PageFetcher
from .utils import compute_hash, format_datetime_br


def create_app():
    app = Flask(__name__)
    app.secret_key = "dev-secret"

    @app.route("/")
    def index():
        storage = MonitorStorage()
        monitors = storage.list_monitors()
        # Formatar datas em tempo do Brasil
        for m in monitors:
            m["last_checked"] = format_datetime_br(m["last_checked"])
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

    @app.route("/edit/<int:monitor_id>", methods=["POST"])
    def edit(monitor_id):
      storage = MonitorStorage()
      monitor = storage.get_monitor(monitor_id)
      if not monitor:
        return redirect(url_for("index"))
      name = request.form.get("name")
      url = request.form.get("url")
      selector = request.form.get("selector") or None
      # Validação simples
      if not name or not url:
        return redirect(url_for("index", err="Nome e URL são obrigatórios"))
      parsed = urlparse(url)
      if not parsed.scheme or not parsed.netloc:
        return redirect(url_for("index", err="URL inválida"))
      storage.update_monitor(monitor_id, name, url, selector)
      return redirect(url_for("index", msg="edit_success"))

    @app.route("/history/<int:monitor_id>")
    def history(monitor_id):
        storage = MonitorStorage()
        monitor = storage.get_monitor(monitor_id)
        if not monitor:
            return redirect(url_for("index"))
        history_list = storage.get_history(monitor_id, limit=100)
        # Formatar datas em tempo do Brasil
        for row in history_list:
            row["checked_at"] = format_datetime_br(row["checked_at"])
        return render_template_string(HISTORY_TEMPLATE, monitor=monitor, history=history_list)

    return app


def run_server(host="127.0.0.1", port=5000):
    app = create_app()
    app.run(host=host, port=port)


INDEX_TEMPLATE = """
<!doctype html>
<title>Fiscal Monitor</title>
<style>
  a { text-decoration: none; color: #464feb; }
  tr th, tr td { border: 1px solid #e6e6e6; }
  tr th { background-color: #f5f5f5; }
  .actions-form { display: inline; }
  .btn { margin-left:6px; }
  /* Modal basic styles */
  .modal { display: none; position: fixed; z-index: 1000; left: 0; top: 0; width: 100%; height: 100%; overflow: auto; background-color: rgba(0,0,0,0.4); }
  .modal-content { background-color: #fefefe; margin: 10% auto; padding: 20px; border: 1px solid #888; width: 400px; }
  .modal-actions { text-align: right; margin-top: 10px; }
</style>
<h1>Monitores</h1>
{% if request.args.get('msg') == 'edit_success' %}
  <div style="padding:8px;background:#e6ffea;border:1px solid #b7f5c9;margin-bottom:10px;">Edição salva com sucesso.</div>
{% endif %}
{% if request.args.get('err') %}
  <div style="padding:8px;background:#ffe6e6;border:1px solid #f5b7b7;margin-bottom:10px;">Erro: {{ request.args.get('err') }}</div>
{% endif %}
<form action="/add" method="post">
  <input name="name" placeholder="Nome" required>
  <input name="url" placeholder="URL" required size="60">
  <input name="selector" placeholder="Seletor CSS (opcional)">
  <button type="submit">Adicionar</button>
</form>
<form action="/check_all" method="post" style="margin-top:10px;">
  <button type="submit">Verificar todos</button>
</form>
<table cellpadding=6 cellspacing=0 style="margin-top:10px;border-collapse:collapse;">
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
      <form action="/check/{{m.id}}" method="post" class="actions-form"><button type="submit">Verificar</button></form>
      <a href="/history/{{m.id}}">Histórico</a>
      <button class="btn" onclick="openEditModal('{{m.id}}','{{m.name|e}}','{{m.url|e}}','{{m.selector|e}}')">Editar</button>
      <form action="/delete/{{m.id}}" method="post" class="actions-form"><button type="submit" onclick="return confirm('Excluir monitor?')">Excluir</button></form>
    </td>
  </tr>
  {% endfor %}
</table>

<!-- Edit modal -->
<div id="editModal" class="modal">
  <div class="modal-content">
    <h3>Editar Monitor</h3>
    <form id="editForm" method="post">
      <input type="hidden" name="monitor_id" id="monitor_id">
      <div>
        <label>Nome</label><br>
        <input name="name" id="edit_name" required style="width:100%">
      </div>
      <div>
        <label>URL</label><br>
        <input name="url" id="edit_url" required style="width:100%">
      </div>
      <div>
        <label>Seletor CSS (opcional)</label><br>
        <input name="selector" id="edit_selector" style="width:100%">
      </div>
      <div class="modal-actions">
        <button type="button" onclick="closeEditModal()">Cancelar</button>
        <button type="submit">Salvar</button>
      </div>
    </form>
  </div>
</div>

<script>
function openEditModal(id, name, url, selector) {
  var modal = document.getElementById('editModal');
  document.getElementById('edit_name').value = name || '';
  document.getElementById('edit_url').value = url || '';
  document.getElementById('edit_selector').value = selector || '';
  var form = document.getElementById('editForm');
  form.action = '/edit/' + id;
  modal.style.display = 'block';
}
function closeEditModal(){
  var modal = document.getElementById('editModal');
  modal.style.display = 'none';
}

// Simple client-side validation
document.getElementById('editForm').addEventListener('submit', function(e){
  var name = document.getElementById('edit_name').value.trim();
  var url = document.getElementById('edit_url').value.trim();
  if(!name){ alert('Nome é obrigatório'); e.preventDefault(); return; }
  try{
    var p = new URL(url);
    if(!p.protocol || !p.hostname){ throw 1; }
  }catch(err){ alert('URL inválida'); e.preventDefault(); return; }
});

// Close modal when clicking outside
window.onclick = function(event) {
  var modal = document.getElementById('editModal');
  if (event.target == modal) { closeEditModal(); }
}
</script>
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
