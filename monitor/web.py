import csv
import io
import json
import re
from datetime import datetime
from urllib.parse import urlparse

from flask import Flask, jsonify, render_template_string, request, redirect, url_for, send_file

from .storage import MonitorStorage
from .fetcher import FetchError, PageFetcher
from .utils import (
    compare_sections,
    compute_hash,
    format_datetime_br,
    segment_html_sections,
)


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
            html = fetcher.fetch(monitor["url"], raw=True)
            current_sections = segment_html_sections(html, monitor.get("selector"))
            current_snapshot = json.dumps(current_sections, ensure_ascii=False)
            current_hash = compute_hash(current_snapshot)

            previous_sections = []
            if monitor.get("last_content"):
                try:
                    previous_sections = json.loads(monitor["last_content"])
                except Exception:
                    previous_sections = []

            diff = compare_sections(previous_sections, current_sections)

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
            current_snapshot = monitor.get("last_content")
            diff = {"alterado": False, "secoes_modificadas": [], "itens_adicionados": [], "itens_removidos": []}

        storage.update_check_result(monitor["id"], status, current_hash, error, current_snapshot)
        return {"status": status, "summary": summary, "error": error, "diff": diff}

    @app.route("/check/<int:monitor_id>", methods=["POST"])
    def check(monitor_id):
        storage = MonitorStorage()
        monitor = storage.get_monitor(monitor_id)
        if not monitor:
            return redirect(url_for("index"))
        result = _check_monitor(storage, monitor)
        return render_template_string(CHECK_RESULT_TEMPLATE, monitor=monitor, result=result)

    @app.route('/api/monitors')
    def api_monitors():
        storage = MonitorStorage()
        monitors = storage.list_monitors()
        return jsonify(monitors)

    @app.route('/api/check/<int:monitor_id>', methods=['POST'])
    def api_check(monitor_id):
        storage = MonitorStorage()
        monitor = storage.get_monitor(monitor_id)
        if not monitor:
            return jsonify({'error': 'not found'}), 404
        result = _check_monitor(storage, monitor)
        return jsonify(result)

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
      # color handling: if remove_color present -> color=None
      remove_color = request.form.get("remove_color")
      existing_color = request.form.get("existing_color") or None
      color_changed = request.form.get("color_changed")
      color_val = request.form.get("color")

      # Validação básica
      if not name or not url:
        return redirect(url_for("index", err="Nome e URL são obrigatórios"))
      parsed = urlparse(url)
      if not parsed.scheme or not parsed.netloc:
        return redirect(url_for("index", err="URL inválida"))

      # Determine resulting color value
      if remove_color:
        color = None
      elif color_changed == '1':
        color = color_val or None
      else:
        color = existing_color or None

      # Validate color format if provided
      if color:
        if not re.match(r'^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$', color):
          return redirect(url_for("index", err="Cor inválida"))

      storage.update_monitor(monitor_id, name, url, selector, color)
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

    @app.route("/export-csv")
    def export_csv():
        """Exportar todos os monitores em CSV"""
        storage = MonitorStorage()
        monitors = storage.list_monitors()
        
        # Criar arquivo CSV em memória
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=['name', 'url', 'selector'], lineterminator='\n')
        writer.writeheader()
        
        for monitor in monitors:
            writer.writerow({
                'name': monitor['name'],
                'url': monitor['url'],
                'selector': monitor['selector'] or ''
            })
        
        # Converter para bytes
        csv_content = output.getvalue()
        
        # Criar resposta com arquivo para download
        return send_file(
            io.BytesIO(csv_content.encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name='monitores.csv'
        )

    @app.route("/import-csv", methods=['POST'])
    def import_csv():
        """Importar monitores de arquivo CSV"""
        if 'file' not in request.files:
            return redirect(url_for("index", err="Nenhum arquivo selecionado"))
        
        file = request.files['file']
        if file.filename == '':
            return redirect(url_for("index", err="Nenhum arquivo selecionado"))
        
        if not file.filename.lower().endswith('.csv'):
            return redirect(url_for("index", err="Arquivo deve ser CSV"))
        
        try:
            # Ler e decodificar o arquivo
            stream = io.TextIOWrapper(file.stream, encoding='utf-8')
            reader = csv.DictReader(stream)
            
            storage = MonitorStorage()
            imported_count = 0
            skipped_count = 0
            errors = []
            
            for row_num, row in enumerate(reader, start=2):  # start=2 porque a primeira linha é cabeçalho
                try:
                    name = row.get('name', '').strip() if row.get('name') else None
                    url = row.get('url', '').strip() if row.get('url') else None
                    selector = row.get('selector', '').strip() if row.get('selector') else None
                    
                    # Validações
                    if not name or not url:
                        skipped_count += 1
                        continue
                    
                    # Validar formato de URL
                    parsed = urlparse(url)
                    if not parsed.scheme or not parsed.netloc:
                        errors.append(f"Linha {row_num}: URL inválida ({url})")
                        skipped_count += 1
                        continue
                    
                    # Verificar se já existe
                    existing = storage.list_monitors()
                    if any(m['url'] == url for m in existing):
                        skipped_count += 1
                        continue
                    
                    # Adicionar monitor
                    storage.add_monitor(name, url, selector or None)
                    imported_count += 1
                    
                except Exception as e:
                    errors.append(f"Linha {row_num}: {str(e)}")
                    skipped_count += 1
            
            # Preparar mensagem de sucesso
            msg = f"Importados {imported_count} monitor(s)"
            if skipped_count > 0:
                msg += f", {skipped_count} ignorado(s)"
            
            return redirect(url_for("index", msg=msg, errors="|".join(errors) if errors else None))
            
        except Exception as e:
            return redirect(url_for("index", err=f"Erro ao processar CSV: {str(e)}"))

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
{% elif request.args.get('msg') %}
  <div style="padding:8px;background:#e6ffea;border:1px solid #b7f5c9;margin-bottom:10px;">✓ {{ request.args.get('msg') }}</div>
{% endif %}
{% if request.args.get('err') %}
  <div style="padding:8px;background:#ffe6e6;border:1px solid #f5b7b7;margin-bottom:10px;">✗ Erro: {{ request.args.get('err') }}</div>
{% endif %}
<form action="/add" method="post">
  <input name="name" placeholder="Nome" required>
  <input name="url" placeholder="URL" required size="60">
  <input name="selector" placeholder="Seletor CSS (opcional)">
  <button type="submit">Adicionar</button>
</form>
<div style="margin-top:10px;">
  <button id="checkAllBtn" onclick="startCheckAll()">Verificar todos</button>
  <a href="/export-csv" style="margin-left:10px;"><button type="button">📥 Exportar CSV</button></a>
  <button type="button" style="margin-left:10px;" onclick="document.getElementById('csvFileInput').click()">📤 Importar CSV</button>
  <form id="importForm" action="/import-csv" method="post" enctype="multipart/form-data" style="display:none;">
    <input type="file" id="csvFileInput" name="file" accept=".csv" onchange="this.form.submit()">
  </form>
</div>
<div id="progressWrapper" style="display:none;margin-top:10px;">
  <div style="width:100%;background:#eee;height:20px;border:1px solid #ccc;">
    <div id="progressBar" style="width:0%;height:100%;background:#4caf50;"></div>
  </div>
  <div id="progressText" style="margin-top:4px;">0%</div>
  <button id="cancelBtn" onclick="cancelCheckAll()" style="margin-top:6px;">Cancelar</button>
</div>
<table cellpadding=6 cellspacing=0 style="margin-top:10px;border-collapse:collapse;">
  <tr><th>ID</th><th>Nome</th><th>URL</th><th>Selector</th><th>Último Check</th><th>Status</th><th>Ações</th></tr>
  {% for m in monitors %}
  <tr>
    <td>{{m.id}}</td>
    <td {% if m.color %} style="background-color:{{m.color}}; padding:4px;"{% endif %}>{{m.name}}</td>
    <td><a href="{{m.url}}" target="_blank">link</a></td>
    <td>{{m.selector or '-'}}</td>
    <td>{{m.last_checked or '-'}}</td>
    <td>{{m.last_status or 'pending'}}</td>
    <td>
      <form action="/check/{{m.id}}" method="post" class="actions-form"><button type="submit">Verificar</button></form>
      <a href="/history/{{m.id}}">Histórico</a>
      <button class="btn" onclick="openEditModal('{{m.id}}','{{m.name|e}}','{{m.url|e}}','{{m.selector|e}}','{{m.color or ''}}')">Editar</button>
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
      <div>
        <label>Cor do Nome</label><br>
        <input type="color" id="edit_color" style="width:60px;">
        <input type="hidden" name="color" id="color_field">
        <label style="margin-left:8px;"><input type="checkbox" id="remove_color" name="remove_color" value="1"> Remover cor</label>
        <input type="hidden" name="existing_color" id="existing_color">
        <input type="hidden" name="color_changed" id="color_changed" value="0">
      </div>
      <div class="modal-actions">
        <button type="button" onclick="closeEditModal()">Cancelar</button>
        <button type="submit">Salvar</button>
      </div>
    </form>
  </div>
</div>

<script>
function openEditModal(id, name, url, selector, color) {
  var modal = document.getElementById('editModal');
  document.getElementById('edit_name').value = name || '';
  document.getElementById('edit_url').value = url || '';
  document.getElementById('edit_selector').value = selector || '';
  // color handling
  document.getElementById('existing_color').value = color || '';
  var colorInput = document.getElementById('edit_color');
  colorInput.value = color || '#000000';
  document.getElementById('remove_color').checked = false;
  document.getElementById('color_changed').value = '0';
  colorInput.onchange = function(){ document.getElementById('color_changed').value = '1'; document.getElementById('color_field').value = colorInput.value; };
  document.getElementById('remove_color').onchange = function(){ if(this.checked){ colorInput.disabled = true; document.getElementById('color_field').value = ''; } else { colorInput.disabled = false; document.getElementById('color_field').value = colorInput.value; }};
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
  // ensure color_field is set if changed
  var colorChanged = document.getElementById('color_changed').value === '1';
  if(colorChanged){ document.getElementById('color_field').value = document.getElementById('edit_color').value; }
});

// Close modal when clicking outside
window.onclick = function(event) {
  var modal = document.getElementById('editModal');
  if (event.target == modal) { closeEditModal(); }
}
</script>

<script>
let checkCancelled = false;
async function startCheckAll(){
  var btn = document.getElementById('checkAllBtn');
  btn.disabled = true;
  checkCancelled = false;
  var wrapper = document.getElementById('progressWrapper');
  var bar = document.getElementById('progressBar');
  var text = document.getElementById('progressText');
  wrapper.style.display = 'block';
  bar.style.width = '0%';
  text.innerText = '0%';
  try{
    let resp = await fetch('/api/monitors');
    if(!resp.ok){ throw new Error('Falha ao obter lista de monitors'); }
    let monitors = await resp.json();
    const total = monitors.length;
    if(total === 0){ text.innerText = 'Nenhum monitor para verificar.'; btn.disabled = false; return; }
    let completed = 0;
    for(const m of monitors){
      if(checkCancelled) break;
      try{
        await fetch('/api/check/' + m.id, { method: 'POST' });
      }catch(err){ /* ignore per-item errors, they'll be recorded in backend */ }
      completed++;
      const percent = Math.round((completed / total) * 100);
      bar.style.width = percent + '%';
      text.innerText = `${completed} de ${total} (${percent}%)`;
    }
    if(!checkCancelled){
      bar.style.width = '100%';
      text.innerText = 'Verificação concluída.';
      setTimeout(()=> location.reload(), 700);
    } else {
      text.innerText = `Cancelado (${completed} de ${total})`;
    }
  }catch(err){
    text.innerText = 'Erro: ' + err.message;
  } finally {
    btn.disabled = false;
    document.getElementById('cancelBtn').disabled = false;
  }
}
function cancelCheckAll(){
  checkCancelled = true;
  document.getElementById('cancelBtn').disabled = true;
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
{% if result.diff and result.diff.alterado %}
  <h2>Resumo das mudanças</h2>
  <p>Seções modificadas: {{result.diff.secoes_modificadas|length}}</p>
  <p>Itens adicionados: {{result.diff.itens_adicionados|length}}</p>
  <p>Itens removidos: {{result.diff.itens_removidos|length}}</p>
  {% if result.diff.secoes_modificadas %}
  <h3>Seções modificadas</h3>
  <ul>
    {% for section in result.diff.secoes_modificadas %}
      <li><strong>{{ section.label }}</strong>
        <pre style="white-space:pre-wrap;background:#f8f8f8;padding:8px;border:1px solid #ddd;">{{ section.diff|join("\n") }}</pre>
      </li>
    {% endfor %}
  </ul>
  {% endif %}
  {% if result.diff.itens_adicionados %}
  <h3>Seções adicionadas</h3>
  <ul>
    {% for item in result.diff.itens_adicionados %}
      <li>{{ item.label }}</li>
    {% endfor %}
  </ul>
  {% endif %}
  {% if result.diff.itens_removidos %}
  <h3>Seções removidas</h3>
  <ul>
    {% for item in result.diff.itens_removidos %}
      <li>{{ item.label }}</li>
    {% endfor %}
  </ul>
  {% endif %}
{% endif %}
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
