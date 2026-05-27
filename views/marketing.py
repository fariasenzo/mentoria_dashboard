import streamlit as st
from datetime import datetime, timedelta
import plotly.graph_objects as go

INSTANCE_IDS = ('cmokhzvfb02yh02ok4wl08cv6', 'cmoq9t9n000j002mlhhtzgt1c', 'cmpg0aool07j102qopi6yz8u7')
PERIODS = ["Hoje", "Ontem", "Este mês", "Trimestre", "Este ano", "Personalizado"]

FUNNEL_COLORS = {
    "LEAD":   "#22c55e",
    "MQL":    "#ef4444",
    "SQL":    "#84cc16",
    "SAL":    "#38bdf8",
    "VENDA":  "#eab308",
}

def format_brl(value):
    try:
        value = float(value)
        return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        return "R$ 0,00"

def load_receita_negociacao(conn):
    if conn is None:
        return 0.0
    query = """
        SELECT COALESCE(SUM(cd.final_price), 0)
        FROM conversations c
        JOIN conversation_stages cs ON c.stage_id = cs.id
        JOIN conversation_deals cd ON c.id = cd.conversation_id
        WHERE c.instance_id IN %s
        AND cs.name = 'LINK DE PAGAMENTO ENVIADO'
    """
    try:
        with conn.cursor() as cur:
            cur.execute(query, (INSTANCE_IDS,))
            result = cur.fetchone()
            return float(result[0]) if result and result[0] is not None else 0.0
    except Exception as e:
        st.error(f"Erro ao carregar receita em negociação: {e}")
        conn.rollback()
        return 0.0

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

def delta(cur, prev):
    if prev is None or prev == 0:
        return None
    pct = ((cur - prev) / prev) * 100
    return f"{'+'if pct>=0 else ''}{pct:.1f}%"

def load_funnel(conn, start, end):
    if not start or not end:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    COUNT(*) AS lead,
                    COUNT(*) FILTER (WHERE cs.name IN ('CONTATO FEITO','INVESTIGAÇÃO','CALL AGENDADA','NO-SHOW','CALL REALIZADA','LINK DE PAGAMENTO ENVIADO','SINAL','VENDA')) AS mql,
                    COUNT(*) FILTER (WHERE cs.name IN ('CALL AGENDADA','NO-SHOW','CALL REALIZADA','LINK DE PAGAMENTO ENVIADO','SINAL','VENDA')) AS sql_count,
                    COUNT(*) FILTER (WHERE cs.name IN ('CALL REALIZADA','LINK DE PAGAMENTO ENVIADO','SINAL','VENDA')) AS sal,
                    COUNT(*) FILTER (WHERE cs.name = 'VENDA') AS venda,
                    COUNT(*) FILTER (WHERE cs.name = 'NO-SHOW') AS no_show
                FROM conversations c
                LEFT JOIN conversation_stages cs ON c.stage_id = cs.id
                WHERE c.instance_id IN %s
                AND c.created_at >= %s
                AND c.created_at <= %s
            """, (INSTANCE_IDS, start, end))
            r = cur.fetchone()
            if not r:
                return None
            return {
                "lead": int(r[0]), "mql": int(r[1]), "sql": int(r[2]),
                "sal": int(r[3]), "venda": int(r[4]), "no_show": int(r[5]),
            }
    except Exception as e:
        st.error(f"Erro ao buscar funil: {e}")
        conn.rollback()
        return None

def show_marketing(conn):
    st.markdown("""
        <div style="margin-bottom:1.5rem">
            <span style="font-size:2rem;font-weight:800;color:#ffffff;letter-spacing:-0.02em">Marketing</span>
            <span style="display:inline-block;width:8px;height:8px;background:#ff5400;border-radius:50%;margin-left:8px;vertical-align:middle"></span>
        </div>
    """, unsafe_allow_html=True)

    if conn is None:
        st.warning("Conexão com o Leadfy não configurada. Adicione `LEADFY_URL` no `.env` e reinicie.")
        return

    st.markdown("##### Período")
    col_p, col_btn = st.columns([5, 1])
    with col_p:
        start1, end1 = period_selector("mk1")
    with col_btn:
        st.write(""); st.write("")
        comparing = st.toggle("⇄ Comparar", key="mk_comparing")

    start2, end2 = None, None
    if comparing:
        st.markdown("##### Período de Comparação")
        start2, end2 = period_selector("mk2")

    data1 = load_funnel(conn, start1, end1)
    data2 = load_funnel(conn, start2, end2) if comparing else None

    if data1 is None or all(v == 0 for v in data1.values()):
        st.warning("Nenhum dado para o período selecionado.")
        return

    labels  = ["LEAD", "MQL", "SQL", "SAL", "VENDA"]
    keys    = ["lead", "mql", "sql", "sal", "venda"]
    values1 = [data1[k] for k in keys]
    values2 = [data2[k] for k in keys] if data2 else [0] * 5

    cols = st.columns(5)
    for i, (col, label) in enumerate(zip(cols, labels)):
        v1, v2 = values1[i], values2[i]
        with col:
            st.metric(label, f"{v1:,}".replace(",", "."), delta=delta(v1, v2) if comparing else None)
            if comparing:
                diff = v1 - v2
                sign = "+" if diff >= 0 else ""
                st.markdown(f'<div style="color:#9ca3af;font-size:0.85rem;margin-top:-8px">Comparação: {str(v2).replace(",", ".")}</div>', unsafe_allow_html=True)
                st.markdown(f'<div style="color:#6b7280;font-size:0.82rem">Diferença: {sign}{diff}</div>', unsafe_allow_html=True)

    st.markdown("---")

    legend_html = "".join([
        f'<span style="display:inline-flex;align-items:center;margin-right:20px">'
        f'<span style="width:11px;height:11px;background:{color};border-radius:3px;display:inline-block;margin-right:7px"></span>'
        f'<span style="color:#9ca3af;font-size:0.82rem;font-weight:500">{label}</span>'
        f'</span>'
        for label, color in FUNNEL_COLORS.items()
    ])
    st.markdown(f'<div style="margin-bottom:12px">{legend_html}</div>', unsafe_allow_html=True)

    text_labels = []
    for i, v in enumerate(values1):
        if i == 0:
            text_labels.append(f"{v:,}".replace(",", "."))
        else:
            pct = (v / values1[i - 1] * 100) if values1[i - 1] > 0 else 0
            text_labels.append(f"{v:,} ({pct:.1f}%)".replace(",", "."))

    fig = go.Figure(go.Funnelarea(
        values=values1,
        text=text_labels,
        labels=labels,
        textinfo="text",
        textfont=dict(color='#ffffff', size=13),
        marker=dict(
            colors=list(FUNNEL_COLORS.values()),
            line=dict(color='#050505', width=2),
        ),
        showlegend=False,
    ))
    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#e5e7eb'),
        height=380,
        margin=dict(l=20, r=150, t=20, b=20),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    no_show  = data1["no_show"]
    sql_val  = data1["sql"]
    ns_rate  = (no_show / sql_val * 100) if sql_val > 0 else 0

    no_show2 = data2["no_show"] if data2 else 0
    sql2     = data2["sql"] if data2 else 0
    ns_rate2 = (no_show2 / sql2 * 100) if sql2 > 0 else 0

    receita_neg = load_receita_negociacao(conn)

    c1, c2, c3, _ = st.columns([1, 1, 1, 2])
    with c1:
        st.metric("Calls Agendadas", f"{sql_val:,}".replace(",", "."), delta=delta(sql_val, sql2) if comparing else None)
        if comparing:
            diff = sql_val - sql2
            sign = "+" if diff >= 0 else ""
            st.markdown(f'<div style="color:#9ca3af;font-size:0.85rem;margin-top:-8px">Comparação: {sql2}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="color:#6b7280;font-size:0.82rem">Diferença: {sign}{diff}</div>', unsafe_allow_html=True)
    with c2:
        st.metric("No-Show", f"{no_show:,}".replace(",", "."), delta=delta(no_show, no_show2) if comparing else None)
        if comparing:
            diff = no_show - no_show2
            sign = "+" if diff >= 0 else ""
            st.markdown(f'<div style="color:#9ca3af;font-size:0.85rem;margin-top:-8px">Comparação: {no_show2}</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="color:#6b7280;font-size:0.82rem">Diferença: {sign}{diff}</div>', unsafe_allow_html=True)
    with c3:
        st.metric("Taxa de No-Show", f"{ns_rate:.1f}%", delta=delta(ns_rate, ns_rate2) if comparing else None)
        if comparing:
            diff = ns_rate - ns_rate2
            sign = "+" if diff >= 0 else ""
            st.markdown(f'<div style="color:#9ca3af;font-size:0.85rem;margin-top:-8px">Comparação: {ns_rate2:.1f}%</div>', unsafe_allow_html=True)
            st.markdown(f'<div style="color:#6b7280;font-size:0.82rem">Diferença: {sign}{diff:.1f}%</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.metric("Receita em Negociação", format_brl(receita_neg))
