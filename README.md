# Fiscal Monitor

Sistema simples de monitoramento de páginas web para detectar alterações de conteúdo com interface web.

## Funcionalidades

- Cadastro de URLs para monitoramento via interface web
- Importação de listas em CSV ou JSON
- Verificação manual via interface web ou CLI
- Armazenamento local em SQLite
- Detecção de mudança por hash de conteúdo limpo
- Ignora scripts, estilos e cabeçalhos irrelevantes
- Filtro de alterações: mostra apenas sites que sofreram mudanças
- Histórico completo de checagens
- Exclusão de monitores

## Instalação

1. Crie e ative um ambiente virtual Python:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Instale as dependências:

```bash
pip install -r requirements.txt
```

## Uso

### Interface Web (Recomendado)

Inicie o servidor web na porta padrão (5000):

```bash
python -m monitor serve
```

Ou customize host e porta:

```bash
python -m monitor serve --host 0.0.0.0 --port 8080
```

Acesse no navegador: `http://localhost:5000`

**Funcionalidades da interface:**
- **Adicionar monitor:** Preencha nome, URL e seletor CSS (opcional)
- **Verificar um monitor:** Clique no botão "Verificar" na linha desejada
- **Verificar todos:** Clique "Verificar todos" para executar todas as verificações e ver apenas os com alterações
- **Ver histórico:** Clique "Histórico" para ver todos os checks anteriores
- **Excluir monitor:** Clique "Excluir" para remover um monitor

### Linha de Comando (CLI)

Para adicionar monitores via terminal:

```bash
python -m monitor add "Manuais NF-e - Ambiente Nacional" "https://www.fazenda.mg.gov.br/empresas/legislacao_tributaria/atos_normativos/" --selector ".data-pub"
```

Listar monitores:

```bash
python -m monitor list
```

Importar CSV:

```bash
python -m monitor import urls.csv
```

Importar JSON:

```bash
python -m monitor import urls.json
```

Executar verificação imediata:

```bash
python -m monitor run
```

Ver histórico:

```bash
python -m monitor history 1
```

## Como funciona

1. O sistema baixa o HTML da página usando `requests`.
2. Remove conteúdos irrelevantes (`script`, `style`, `iframe`, etc.).
3. Se for informado um seletor CSS, monitora apenas essa parte da página.
4. Gera um hash SHA256 do texto limpo.
5. Compara com o hash salvo da última verificação.
6. Se houver diferença, marca como `updated` e exibe na interface web.
7. Todo o histórico de verificações é armazenado localmente em SQLite.

## Estrutura do projeto

- `monitor/` - código do aplicativo
  - `web.py` - interface web Flask
  - `cli.py` - interface de linha de comando
  - `storage.py` - camada de dados SQLite
  - `fetcher.py` - download de páginas
  - `utils.py` - funções utilitárias
- `data/` - banco de dados SQLite gerado em tempo de execução
- `requirements.txt` - dependências Python
- `README.md` - instruções

## Notas

- O projeto foi pensado para funcionar com sites governamentais, usando cabeçalhos de navegador e timeout maior.
- Todas as datas são exibidas em horário de Brasília (UTC-3).
- Para páginas muito restritivas, ajuste o seletor CSS ou use uma opção de proxy / headless browser fora deste projeto.
- A interface web é recomendada para uso diário, pois oferece uma experiência mais intuitiva.

## Exemplo de CSV

Para usar com `python -m monitor import urls.csv`, crie um arquivo com as colunas: `name`, `url`, `selector` (opcional).

```csv
"SEFAZ MG - NTs","https://www.fazenda.mg.gov.br/empresas/legislacao_tributaria/atos_normativos/",".data-pub"
"Receita Federal - EFD-Reinf","https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/declaracoes-e-demonstrativos/efd-reinf",".document-date"
```

## Exemplo de JSON

Para usar com `python -m monitor import urls.json`, crie um arquivo no formato:

```json
[
  {
    "name": "SEFAZ MG - NTs",
    "url": "https://www.fazenda.mg.gov.br/empresas/legislacao_tributaria/atos_normativos/",
    "selector": ".data-pub"
  },
  {
    "name": "Receita Federal - EFD-Reinf",
    "url": "https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/declaracoes-e-demonstrativos/efd-reinf",
    "selector": ".document-date"
  }
]
```
