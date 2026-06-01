import argparse
import csv
import json
import os
from datetime import datetime

from .fetcher import FetchError, PageFetcher
from .storage import MonitorStorage
from .utils import compute_hash


def load_import_input(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".csv":
        return "csv"
    if ext == ".json":
        return "json"
    raise ValueError("Formato desconhecido. Use CSV ou JSON.")


def run_check(storage, show_diff=False):
    notifier = None
    fetcher = PageFetcher(timeout=30)
    monitors = storage.list_monitors()

    if not monitors:
        print("Nenhum link cadastrado. Use 'monitor add' ou 'monitor import'.")
        return

    for monitor in monitors:
        print(f"Verificando {monitor['id']} - {monitor['name']} -> {monitor['url']}")
        current_hash = None
        summary = None
        status = "ok"
        error = None

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
        except FetchError as exc:
            status = "error"
            error = str(exc)
            summary = "Falha ao baixar a página."
            current_hash = monitor.get("last_hash")

        storage.update_check_result(monitor["id"], status, current_hash, error)
        print(f"  → status: {status}" + (f" ({error})" if error else ""))
        # notificações foram removidas (sem webhook/Teams)


def command_add(args):
    storage = MonitorStorage()
    storage.add_monitor(args.name, args.url, args.selector)
    print("Monitor adicionado com sucesso.")


def command_list(args):
    storage = MonitorStorage()
    monitors = storage.list_monitors()
    if not monitors:
        print("Nenhum monitor cadastrado.")
        return
    print("ID | STATUS   | ÚLTIMO CHECK | NOME")
    print("---|----------|--------------|-----")
    for monitor in monitors:
        print(
            f"{monitor['id']:>2} | {monitor['last_status'] or 'pending':<8} | "
            f"{monitor['last_checked'] or '-':<12} | {monitor['name']}"
        )


def command_import(args):
    storage = MonitorStorage()
    kind = load_import_input(args.path)
    if kind == "csv":
        count = storage.import_from_csv(args.path)
    else:
        count = storage.import_from_json(args.path)
    print(f"Importado(s) {count} link(s) do arquivo {args.path}.")


def command_history(args):
    storage = MonitorStorage()
    history = storage.get_history(args.id, limit=args.limit)
    if not history:
        print("Nenhum histórico encontrado para este monitor.")
        return
    for row in history:
        print(
            f"[{row['checked_at']}] {row['status']} hash={row['hash'] or '-'} "
            f"erro={row['error'] or '-'}"
        )


def command_config(args):
    storage = MonitorStorage()
    print("Config removida: webhook do Teams não é mais usada.")


def command_run(args):
    storage = MonitorStorage()
    run_check(storage)


def command_serve(args):
    # execução da interface web
    from .web import run_server

    run_server(host=args.host, port=args.port)


def main():
    parser = argparse.ArgumentParser(
        description="Monitoramento de páginas web para detectar mudanças de conteúdo"
    )
    subparsers = parser.add_subparsers(dest="command")

    parser_add = subparsers.add_parser("add", help="Adicionar um URL ao monitoramento")
    parser_add.add_argument("name", help="Nome descritivo do site")
    parser_add.add_argument("url", help="URL da página a ser monitorada")
    parser_add.add_argument("--selector", help="Seletor CSS para monitorar apenas parte da página")
    parser_add.set_defaults(func=command_add)

    parser_list = subparsers.add_parser("list", help="Listar URLs monitorados")
    parser_list.set_defaults(func=command_list)

    parser_import = subparsers.add_parser("import", help="Importar uma lista de URLs de um arquivo CSV ou JSON")
    parser_import.add_argument("path", help="Caminho para CSV ou JSON")
    parser_import.set_defaults(func=command_import)

    parser_history = subparsers.add_parser("history", help="Mostrar histórico de um monitor")
    parser_history.add_argument("id", type=int, help="ID do monitor")
    parser_history.add_argument("--limit", type=int, default=20, help="Número de registros a mostrar")
    parser_history.set_defaults(func=command_history)

    parser_config = subparsers.add_parser("config", help="(Removido) Configurações do sistema")
    parser_config.set_defaults(func=command_config)

    parser_run = subparsers.add_parser("run", help="Executar verificação imediata")
    parser_run.set_defaults(func=command_run)

    parser_serve = subparsers.add_parser("serve", help="Iniciar interface web para gerenciar monitores")
    parser_serve.add_argument("--host", default="127.0.0.1", help="Host para o servidor web")
    parser_serve.add_argument("--port", type=int, default=5000, help="Porta para o servidor web")
    parser_serve.set_defaults(func=command_serve)

    args = parser.parse_args()
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    try:
        args.func(args)
    except Exception as exc:
        print(f"Erro: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
