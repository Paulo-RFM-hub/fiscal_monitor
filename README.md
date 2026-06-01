# Fiscal Monitor

Sistema simples de monitoramento de páginas web para detectar alterações de conteúdo e enviar notificações para Microsoft Teams.

## Funcionalidades

- Cadastro de URLs para monitoramento
- Importação de listas em CSV ou JSON
- Verificação manual com `run`
- Armazenamento local em SQLite
- Detecção de mudança por hash de conteúdo limpo
- Ignora scripts, estilos e cabeçalhos irrelevantes
- Integração com Microsoft Teams via webhook
- Histórico de checagens

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

### Adicionar um monitor

```bash
python -m monitor add "Manuais NF-e - Ambiente Nacional " "https://www.fazenda.mg.gov.br/empresas/legislacao_tributaria/atos_normativos/" --selector ".data-pub"
```

### Listar monitores

```bash
python -m monitor list
```

### Importar CSV

O CSV deve ter pelo menos duas colunas: `name,url` e opcional `selector`.

```bash
python -m monitor import urls.csv
```

### Importar JSON

O JSON deve ser uma lista de objetos com `name` e `url`.

```bash
python -m monitor import urls.json
```

### Configurar webhook do Teams

```bash
python -m monitor config --webhook "https://outlook.office.com/webhook/SEU_WEBHOOK"
```

### Executar verificação imediata

```bash
python -m monitor run
```

Se o webhook estiver configurado, alterações detectadas serão enviadas automaticamente para o Teams.

### Ver histórico de um monitor

```bash
python -m monitor history 1
```

## Como funciona

1. O sistema baixa o HTML da página usando `requests`.
2. Remove conteúdos irrelevantes (`script`, `style`, `iframe`, etc.).
3. Se for informado um seletor CSS, monitora apenas essa parte da página.
4. Gera um hash SHA256 do texto limpo.
5. Compara com o hash salvo da última verificação.
6. Se houver diferença, marca como `updated` e envia notificação.

## Configuração do Microsoft Teams

1. Crie um conector de entrada (Incoming Webhook) no canal do Teams.
2. Copie o URL gerado.
3. Execute o comando de configuração do CLI:

```bash
python -m monitor config --webhook "SEU_WEBHOOK_DO_TEAMS"
```

## Estrutura do projeto

- `monitor/` - código do aplicativo
- `data/` - banco de dados SQLite gerado em tempo de execução
- `requirements.txt` - dependências Python
- `README.md` - instruções

## Notas

- O projeto foi pensado para funcionar com sites governamentais, usando cabeçalhos de navegador e tempo maior de timeout.
- Para páginas muito restritivas, ajuste o seletor CSS ou use uma opção de proxy / headless browser fora deste projeto.

## Exemplo de CSV

```csv
"SEFAZ MG - NTs","https://www.fazenda.mg.gov.br/empresas/legislacao_tributaria/atos_normativos/",".data-pub"
"Receita Federal - EFD-Reinf","https://www.gov.br/receitafederal/pt-br/assuntos/orientacao-tributaria/declaracoes-e-demonstrativos/efd-reinf",".document-date"
```
