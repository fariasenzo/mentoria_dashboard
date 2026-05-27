# CLAUDE.md — Projeto Dashboard Mentoria

## Fluxo de Trabalho

- **Gemini** (`mcp__gemini-collab__ask_gemini`) → escreve todo o código.
- **Claude** → aplica o código nos arquivos, revisa, responde dúvidas, toma decisões de arquitetura.

Nunca escrever código diretamente — sempre delegar ao Gemini. Claude aplica o código gerado nos arquivos.

## Stack

- **Dashboard:** Streamlit 1.50.0
- **Banco principal:** PostgreSQL (schema `mentoria_clean`), conexão via `psycopg2`
- **Banco de marketing:** PostgreSQL Leadfy (read-only), conexão separada via `psycopg2`
- **Gráficos:** Plotly (`plotly.graph_objects`)
- **Conexões:** URLs via `.env`

## Variáveis de Ambiente (`.env`)

```
DATABASE_URL=postgresql://...      # Banco principal (Railway)
LEADFY_URL=postgresql://...        # Banco Leadfy (read-only, marketing)
```

## Estrutura de Arquivos

```
mentoria/
├── streamlit_app.py        # Entrada principal — sidebar, navegação, conexões
├── assets/style.css        # CSS global (dark theme, KPI cards, sidebar)
├── .env                    # Variáveis de ambiente (não versionar)
├── CLAUDE.md               # Este arquivo
└── views/
    ├── vendas.py           # Aba Vendas (dados de mentoria_clean)
    └── marketing.py        # Aba Marketing (dados do Leadfy)
```

**Regra:** ao criar ou editar uma aba, trabalhar apenas no arquivo correspondente.

## Schema do Banco Principal

Usar sempre `mentoria_clean` (não `mentoria` diretamente). As views já tratam:
- Datas TEXT → TIMESTAMPTZ
- NUMERIC → float
- `clientes` deduplicados com DISTINCT ON

**Exceção:** `mentoria.automacao_hubla` é lida diretamente (sem view limpa) via UNION ALL em `load_data()` em `vendas.py`, pois é a tabela de captura de webhooks da Hubla.

### Views disponíveis em `mentoria_clean`

| View | Descrição |
|------|-----------|
| `faturas` | Faturas com todas as datas tipadas como TIMESTAMPTZ |
| `clientes` | Clientes deduplicados (DISTINCT ON id_cliente) |
| `financeiro_fatura` | Valores monetários já como float |

### Colunas importantes em `mentoria_clean.faturas`

- `id_fatura`, `id_cliente`, `id_produto` — TEXT
- `status_fatura`, `metodo_pagamento`, `tipo_fatura` — TEXT
- `data_pagamento`, `data_criacao`, `data_vencimento`, `data_reembolso`, `data_prevista_liberacao` — TIMESTAMPTZ
- `created_at`, `updated_at` — TIMESTAMPTZ (nativo)

### Colunas em `mentoria_clean.financeiro_fatura`

`valor_produto`, `valor_desconto`, `valor_total`, `taxa_hubla_variavel`, `taxa_hubla_fixa`, `valor_liquido`, `valor_comissao_afiliados`, `valor_comissao_coprodutores`, `valor_sua_comissao` — todos float

### Tabela `mentoria.automacao_hubla`

Captura de webhooks da Hubla. Usada em UNION ALL com `mentoria_clean.faturas` no `load_data()` de `vendas.py` para incluir vendas que entraram pela automação mas ainda não foram sincronizadas nas tabelas principais.

- `total_amount` armazena o **valor líquido** (após taxas Hubla) — a automação foi configurada para gravar o líquido aqui
- Entradas de teste são filtradas: `transaction_id NOT LIKE '%-tester'` e `user_email NOT LIKE '%@example.com'`
- Deduplicação: só inclui registros cujo `transaction_id` não existe em `mentoria_clean.faturas`
- `%` nos LIKE deve ser escapado como `%%` no psycopg2

## Quirks e Armadilhas Conhecidas

- **Nunca usar o schema `mentoria` diretamente nas queries** — sempre `mentoria_clean` (exceto `automacao_hubla`, que não tem view limpa)
- **psycopg2 retorna `decimal.Decimal`** para colunas NUMERIC — já tratado nas views, mas se precisar em Python: `.astype(float)` no DataFrame
- **CSS da sidebar:** o botão de toggle usa `data-testid="stExpandSidebarButton"` e fica dentro do `stToolbar`. Não esconder o toolbar inteiro — esconder apenas `stToolbarActions`, `stAppDeployButton`, `stMainMenu`
- **CSS é carregado em `streamlit_app.py`** (não nas views individuais), para garantir que aplica em todas as páginas desde o início

## Conexões no `streamlit_app.py`

```python
@st.cache_resource
def get_conn():         # Banco principal
    return psycopg2.connect(DATABASE_URL)

@st.cache_resource
def get_leadfy_conn():  # Leadfy (marketing, read-only)
    return psycopg2.connect(LEADFY_URL)
```

Ambas são passadas como parâmetro para as views: `show_vendas(conn)`, `show_marketing(leadfy_conn)`.
