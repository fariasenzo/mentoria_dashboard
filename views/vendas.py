import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

def format_brl(value):
    if value is None:
        return "R$ 0,00"
    try:
        value = float(value)
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"

def format_int(value):
    if value is None:
        return "0"
    try:
        return f"{int(value):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"

def load_css():
    with open("assets/style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

def fetch(conn, query, params=None):
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            return pd.DataFrame(rows, columns=cols)
    except Exception as e:
        st.error(f"Erro na query: {e}")
        conn.rollback()
        return pd.DataFrame()

def get_date_range(period):
    today = datetime.now()
    if period == "Hoje":
        return today.replace(hour=0, minute=0, second=0), today.replace(hour=23, minute=59, second=59)
    elif period == "Ontem":
        y = today - timedelta(days=1)
        return y.replace(hour=0, minute=0, second=0), y.replace(hour=23, minute=59, second=59)
    elif period == "Este mês":
        return today.replace(day=1, hour=0, minute=0, second=0), today.replace(hour=23, minute=59, second=59)
    elif period == "Trimestre":
        q = ((today.month - 1) // 3) * 3 + 1
        return today.replace(month=q, day=1, hour=0, minute=0, second=0), today.replace(hour=23, minute=59, second=59)
    elif period == "Este ano":
        return today.replace(month=1, day=1, hour=0, minute=0, second=0), today.replace(hour=23, minute=59, second=59)
    return None, None

PERIODS = ["Hoje", "Ontem", "Este mês", "Trimestre", "Este ano", "Personalizado"]

def period_selector(prefix):
    period = st.radio("", PERIODS, horizontal=True, key=f"{prefix}_radio", label_visibility="collapsed")
    if period == "Personalizado":
        c1, c2 = st.columns(2)
        with c1:
            d1 = st.date_input("De", key=f"{prefix}_start", format="DD/MM/YYYY")
        with c2:
            d2 = st.date_input("Até", key=f"{prefix}_end", format="DD/MM/YYYY")
        return datetime.combine(d1, datetime.min.time()), datetime.combine(d2, datetime.max.time())
    return get_date_range(period)

def load_data(conn, start, end):
    if not start or not end:
        return pd.DataFrame()
    return fetch(conn, """
        SELECT f.id_fatura, f.id_cliente, c.nome_cliente, ff.valor_liquido, f.data_pagamento
        FROM mentoria_clean.faturas f
        JOIN mentoria_clean.clientes c ON f.id_cliente = c.id_cliente
        JOIN mentoria_clean.financeiro_fatura ff ON f.id_fatura = ff.id_fatura
        WHERE f.data_pagamento IS NOT NULL
        AND f.data_pagamento >= %s
        AND f.data_pagamento <= %s

        UNION ALL

        SELECT
            ah.transaction_id      AS id_fatura,
            ah.user_email          AS id_cliente,
            ah.user_name           AS nome_cliente,
            ah.total_amount::float AS valor_liquido,
            ah.paid_at             AS data_pagamento
        FROM mentoria.automacao_hubla ah
        WHERE ah.paid_at IS NOT NULL
        AND ah.paid_at >= %s
        AND ah.paid_at <= %s
        AND ah.transaction_id NOT LIKE '%%-tester'
        AND ah.user_email NOT LIKE '%%@example.com'
        AND ah.transaction_id NOT IN (
            SELECT id_fatura FROM mentoria_clean.faturas WHERE data_pagamento IS NOT NULL
        )
    """, (start, end, start, end))

def kpis(df):
    if df.empty:
        return 0.0, 0, 0.0
    fat = float(df['valor_liquido'].sum())
    v   = df['id_fatura'].nunique()
    c   = df['id_cliente'].nunique()
    return fat, v, fat / c if c > 0 else 0.0

def delta(cur, prev):
    if prev is None or prev == 0:
        return None
    try:
        pct = ((float(cur) - float(prev)) / float(prev)) * 100
        return f"{'+'if pct>=0 else ''}{pct:.1f}%"
    except (ValueError, TypeError):
        return None

def bar_chart(fig_data, title, orientation='v', fig_data2=None):
    labels = fig_data.iloc[:, 0]
    values = fig_data.iloc[:, 1]
    x_data = values if orientation == 'h' else labels
    y_data = labels if orientation == 'h' else values

    trace1 = go.Bar(
        x=x_data, y=y_data,
        orientation=orientation,
        marker_color='#ff5400',
        marker_line_width=0,
        name="Período Referência",
        cliponaxis=False,
        text=[format_brl(float(v)) for v in values],
        textposition='outside',
        textfont=dict(color='#9ca3af', size=11),
    )
    data = [trace1]

    layout_args = dict(
        title=dict(text=title, font=dict(color='#f1f5f9', size=16)),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, zeroline=False,
                   showticklabels=(orientation == 'v'),
                   tickfont=dict(color='#e5e7eb', size=13)),
        yaxis=dict(showgrid=False, zeroline=False,
                   showticklabels=(orientation == 'h'),
                   tickfont=dict(color='#e5e7eb', size=12)),
        height=300 if orientation == 'v' else 380,
    )

    if fig_data2 is not None:
        labels2 = fig_data2.iloc[:, 0]
        values2 = fig_data2.iloc[:, 1]
        x_data2 = values2 if orientation == 'h' else labels2
        y_data2 = labels2 if orientation == 'h' else values2

        trace2 = go.Bar(
            x=x_data2, y=y_data2,
            orientation=orientation,
            marker_color='rgba(255,84,0,0.2)',
            marker_pattern_shape="/",
            marker_pattern_fgcolor='#ff5400',
            marker_line_width=0,
            name="Período Comparação",
            cliponaxis=False,
            text=[format_brl(float(v)) for v in values2],
            textposition='outside',
            textfont=dict(color='#9ca3af', size=11),
        )
        data.append(trace2)
        layout_args['barmode'] = 'group'
        layout_args['showlegend'] = True
        layout_args['legend'] = dict(font=dict(color='#9ca3af'), bgcolor='rgba(0,0,0,0)')

        if orientation == 'v':
            max_val = float(max(values.max(), values2.max()))
            layout_args['yaxis']['range'] = [0, max_val * 1.25]

    if orientation == 'v':
        layout_args['margin'] = dict(l=10, r=20, t=50, b=20)
    else:
        layout_args['margin'] = dict(l=10, r=130, t=50, b=20)

    fig = go.Figure(data=data)
    fig.update_layout(layout_args)
    return fig

def load_receita_negociacao(conn):
    if conn is None:
        return 0.0
    _INSTANCE_IDS = ('cmokhzvfb02yh02ok4wl08cv6', 'cmoq9t9n000j002mlhhtzgt1c', 'cmpg0aool07j102qopi6yz8u7')
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(SUM(cd.final_price), 0)
                FROM conversations c
                JOIN conversation_stages cs ON c.stage_id = cs.id
                JOIN conversation_deals cd ON c.id = cd.conversation_id
                WHERE c.instance_id IN %s
                AND cs.name = 'LINK DE PAGAMENTO ENVIADO'
            """, (_INSTANCE_IDS,))
            result = cur.fetchone()
            return float(result[0]) if result and result[0] is not None else 0.0
    except Exception as e:
        st.error(f"Erro ao carregar receita em negociação: {e}")
        conn.rollback()
        return 0.0

def show_vendas(conn, leadfy_conn=None):
    st.markdown("""
        <div style="margin-bottom:1.5rem">
            <span style="font-size:2rem;font-weight:800;color:#ffffff;letter-spacing:-0.02em">Vendas</span>
            <span style="display:inline-block;width:8px;height:8px;background:#ff5400;border-radius:50%;margin-left:8px;vertical-align:middle"></span>
        </div>
    """, unsafe_allow_html=True)

    st.markdown("##### Período")
    col_p, col_btn = st.columns([5, 1])
    with col_p:
        start1, end1 = period_selector("p1")
    with col_btn:
        st.write(""); st.write("")
        comparing = st.toggle("⇄ Comparar", key="comparing")

    start2, end2 = None, None
    if comparing:
        st.markdown("##### Período de Comparação")
        start2, end2 = period_selector("p2")

    df1 = load_data(conn, start1, end1)
    df2 = load_data(conn, start2, end2) if comparing else pd.DataFrame()

    fat1, v1, t1 = kpis(df1)
    fat2, v2, t2 = kpis(df2)
    receita_neg = load_receita_negociacao(leadfy_conn)

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Faturamento Total", format_brl(fat1), delta=delta(fat1, fat2) if comparing else None)
        if comparing:
            diff = fat1 - fat2
            sign = "+" if diff >= 0 else ""
            st.markdown(f'<div style="color:#9ca3af;font-size:0.85rem;margin-top:-8px">Comparação: {format_brl(fat2)}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="color:#6b7280;font-size:0.82rem">Diferença: {sign}{format_brl(diff)}</div>', unsafe_allow_html=True)
    with k2:
        st.metric("Vendas Únicas", format_int(v1), delta=delta(v1, v2) if comparing else None)
        if comparing:
            diff = v1 - v2
            sign = "+" if diff >= 0 else ""
            st.markdown(f'<div style="color:#9ca3af;font-size:0.85rem;margin-top:-8px">Comparação: {format_int(v2)}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="color:#6b7280;font-size:0.82rem">Diferença: {sign}{format_int(diff)}</div>', unsafe_allow_html=True)
    with k3:
        st.metric("Ticket Médio", format_brl(t1), delta=delta(t1, t2) if comparing else None)
        if comparing:
            diff = t1 - t2
            sign = "+" if diff >= 0 else ""
            st.markdown(f'<div style="color:#9ca3af;font-size:0.85rem;margin-top:-8px">Comparação: {format_brl(t2)}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="color:#6b7280;font-size:0.82rem">Diferença: {sign}{format_brl(diff)}</div>', unsafe_allow_html=True)
    with k4:
        st.metric("Receita em Negociação", format_brl(receita_neg))

    if df1.empty:
        st.warning("Nenhum dado para o período selecionado.")
        return

    st.markdown("---")

    df1_p = df1.copy()
    df1_p['day'] = pd.to_datetime(df1_p['data_pagamento']).dt.day
    df1_p['semana'] = df1_p['day'].apply(lambda d: 'S1' if d<=7 else 'S2' if d<=14 else 'S3' if d<=21 else 'S4')
    weekly = df1_p.groupby('semana')['valor_liquido'].sum().reindex(['S1','S2','S3','S4'], fill_value=0).reset_index()
    weekly.columns = ['semana', 'receita']

    weekly2 = None
    if comparing and not df2.empty:
        df2_p = df2.copy()
        df2_p['day'] = pd.to_datetime(df2_p['data_pagamento'], format='%d/%m/%Y %H:%M:%S').dt.day
        df2_p['semana'] = df2_p['day'].apply(lambda d: 'S1' if d<=7 else 'S2' if d<=14 else 'S3' if d<=21 else 'S4')
        weekly2 = df2_p.groupby('semana')['valor_liquido'].sum().reindex(['S1','S2','S3','S4'], fill_value=0).reset_index()
        weekly2.columns = ['semana', 'receita']

    st.plotly_chart(bar_chart(weekly, "Receita por Semana", fig_data2=weekly2), use_container_width=True)

    st.markdown("---")

    daily = df1_p.groupby('day')['valor_liquido'].sum().reindex(range(1, 32), fill_value=0).reset_index()
    daily.columns = ['dia', 'receita']
    fig_line = go.Figure(go.Scatter(
        x=daily['dia'],
        y=daily['receita'],
        mode='lines',
        line=dict(color='#FFE600', width=2.5),
        fill='tozeroy',
        fillcolor='rgba(255,230,0,0.04)',
        hovertemplate='Dia %{x}: %{y:,.2f}<extra></extra>',
    ))
    fig_line.update_layout(
        title=dict(text="Receita por Dia do Mês", font=dict(color='#f1f5f9', size=16)),
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=10, r=20, t=50, b=20),
        height=280,
        xaxis=dict(showgrid=False, zeroline=False, tickfont=dict(color='#e5e7eb', size=11), dtick=1),
        yaxis=dict(showgrid=False, zeroline=False, tickfont=dict(color='#e5e7eb', size=11)),
    )
    st.plotly_chart(fig_line, use_container_width=True)

    st.markdown("---")

    top10 = (df1.groupby('nome_cliente')['valor_liquido'].sum()
               .reset_index().sort_values('valor_liquido', ascending=True).tail(10))
    top10.columns = ['cliente', 'receita']

    st.plotly_chart(bar_chart(top10, "Top 10 Clientes por Receita", orientation='h'), use_container_width=True)
