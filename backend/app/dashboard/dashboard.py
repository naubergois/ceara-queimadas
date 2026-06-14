"""
Streamlit Dashboard — Queimadas Ceará
==============================================
Dashboard interativo para monitoramento de queimadas no Ceará.

Fontes de dados:
- NASA FIRMS (VIIRS SNPP + NOAA-20 + MODIS) — focos ativos
- Open-Meteo — dados climáticos por município
- API de Inovação — previsão de risco NeKo-PIGNN
- GOES-16 (ABI-L2-FDCF) — detecção adicional via canal infravermelho

Uso:
    streamlit run app/dashboard/dashboard.py
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium

# ── Config ─────────────────────────────────────────────────────────────────

logger = logging.getLogger(__name__)

# URL base da API FastAPI (aceita via env ou default localhost)
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
API_FOCOS = f"{API_BASE}/api/v1/real/focos"
API_CLIMA = f"{API_BASE}/api/v1/real/clima"
API_ALERTAS = f"{API_BASE}/api/v1/real/alertas"
API_STATUS = f"{API_BASE}/api/v1/real/status"
API_RISCO = f"{API_BASE}/api/v1/prever-risco-municipios"
API_INOV_STATUS = f"{API_BASE}/api/v1/status-modelos"
API_KOOPMAN_MODOS = f"{API_BASE}/api/v1/modos-coerentes"

# Bounding box Ceará
CEARA_BBOX = {"lat_min": -7.85, "lat_max": -2.78, "lon_min": -41.42, "lon_max": -37.25}

# ── Cache helpers ──────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def fetch_focos(dias: int = 3, severidade: Optional[str] = None) -> dict:
    """Busca focos reais da API FIRMS com cache de 5 min."""
    params = {"dias": dias}
    if severidade:
        params["severidade"] = severidade
    try:
        resp = requests.get(API_FOCOS, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"Erro ao buscar focos: {e}")
        return {"total": 0, "focos": [], "atualizado_em": None}


@st.cache_data(ttl=600)
def fetch_clima() -> dict:
    """Busca dados climáticos dos municípios do Ceará."""
    try:
        resp = requests.get(API_CLIMA, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"Clima indisponível: {e}")
        return {"total": 0, "municipios": []}


@st.cache_data(ttl=300)
def fetch_alertas(horas: int = 48, dias: int = 3) -> dict:
    """Busca alertas gerados a partir dos focos e clima."""
    try:
        resp = requests.get(API_ALERTAS, params={"horas": horas, "dias": dias}, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"Alertas indisponíveis: {e}")
        return {"total": 0, "alertas": []}


@st.cache_data(ttl=600)
def fetch_status() -> dict:
    """Status das fontes de dados e cache."""
    try:
        resp = requests.get(API_STATUS, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"status": "erro", "detalhe": str(e)}


@st.cache_data(ttl=600)
def fetch_risco(horas_frente: int = 6) -> dict:
    """Previsão de risco por município (NeKo-PIGNN)."""
    try:
        resp = requests.get(API_RISCO, params={"horas_frente": horas_frente}, timeout=60)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"Previsão de risco indisponível: {e}")
        return {"total": 0, "riscos": []}


# ── Helpers de visualização ────────────────────────────────────────────────

def severidade_color(sev: str) -> str:
    return {"baixa": "green", "media": "orange", "alta": "red", "critica": "darkred"}.get(sev, "blue")


def build_foco_map(focos: list[dict], center: tuple = (-5.0, -39.5), zoom: int = 7) -> folium.Map:
    """Constrói mapa Folium com os focos de queimada."""
    m = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap")

    # Adiciona tiles de satélite como layer opcional
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="Satélite",
        overlay=False,
    ).add_to(m)

    # Legenda manual (adicionada via HTML)
    legend_html = """
    <div style="position: fixed; bottom: 20px; left: 20px; z-index: 9999;
                background: white; padding: 10px; border-radius: 5px;
                box-shadow: 0 0 10px rgba(0,0,0,0.3); font-size: 12px;">
        <b>Severidade</b><br>
        <span style="color:green">●</span> Baixa<br>
        <span style="color:orange">●</span> Média<br>
        <span style="color:red">●</span> Alta<br>
        <span style="color:darkred">●</span> Crítica
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    for foco in focos:
        lat = foco.get("latitude", foco.get("lat"))
        lon = foco.get("longitude", foco.get("lon"))
        sev = foco.get("severidade", "baixa")
        color = severidade_color(sev)
        confianca = foco.get("confianca", 0)
        frp = foco.get("frp", "N/A")
        data_hora = foco.get("data_hora", "")
        sensor = foco.get("sensor", "")
        satelite = foco.get("satelite", "")
        municipio = foco.get("municipio", "?")

        popup_text = f"""
        <b>Município:</b> {municipio}<br>
        <b>Severidade:</b> {sev.upper()}<br>
        <b>Confiança:</b> {confianca:.0f}%<br>
        <b>FRP:</b> {frp}<br>
        <b>Sensor:</b> {sensor} ({satelite})<br>
        <b>Data/Hora:</b> {data_hora}<br>
        <b>Coords:</b> {lat:.4f}, {lon:.4f}
        """

        folium.CircleMarker(
            location=[lat, lon],
            radius=6 + (confianca or 0) / 20,
            color=color,
            fill=True,
            fill_opacity=0.7,
            popup=folium.Popup(popup_text, max_width=300),
            tooltip=f"{municipio} — {sev} (FRP: {frp})",
        ).add_to(m)

    folium.LayerControl().add_to(m)
    return m


def build_risk_map(riscos: list[dict]) -> folium.Map:
    """Mapa de calor de risco por município."""
    m = folium.Map(location=(-5.0, -39.5), zoom_start=7, tiles="OpenStreetMap")

    for r in riscos:
        lat, lon = r["lat"], r["lon"]
        indice = r["indice_risco"]
        classificacao = r["classificacao"]
        color = {"baixo": "green", "medio": "orange", "alto": "red", "critico": "darkred"}.get(classificacao, "blue")

        popup = f"""
        <b>{r['municipio']}</b><br>
        Risco: {indice:.2%} ({classificacao.upper()})<br>
        FRP previsto: {r['frp_previsto']:.3f}<br>
        Rothermel: {r['rothermel_score']:.2%}
        """
        folium.CircleMarker(
            location=[lat, lon],
            radius=8 + indice * 15,
            color=color,
            fill=True,
            fill_opacity=0.6,
            popup=folium.Popup(popup, max_width=250),
            tooltip=f"{r['municipio']}: {indice:.0%}",
        ).add_to(m)

    return m


def metric_card(label: str, value: str, delta: Optional[str] = None) -> None:
    """Card de métrica com cor condicional."""
    col = st.columns(1)[0]
    if delta:
        st.metric(label=label, value=value, delta=delta)
    else:
        st.metric(label=label, value=value)


def focus_chart(focos: list[dict]) -> go.Figure:
    """Gráfico de barras: focos por severidade."""
    df = pd.DataFrame(focos)
    if df.empty:
        return go.Figure()

    sev_counts = df["severidade"].value_counts().reset_index()
    sev_counts.columns = ["severidade", "contagem"]

    order = ["critica", "alta", "media", "baixa"]
    sev_counts["severidade"] = pd.Categorical(sev_counts["severidade"], categories=order, ordered=True)
    sev_counts = sev_counts.sort_values("severidade")

    colors = {"critica": "darkred", "alta": "red", "media": "orange", "baixa": "green"}
    fig = px.bar(
        sev_counts,
        x="severidade",
        y="contagem",
        color="severidade",
        color_discrete_map=colors,
        title="Focos por Severidade",
        labels={"severidade": "Severidade", "contagem": "Nº de Focos"},
    )
    fig.update_layout(showlegend=False)
    return fig


def alertas_chart(alertas: list[dict]) -> go.Figure:
    """Gráfico de barras: alertas por nível."""
    if not alertas:
        return go.Figure()

    df = pd.DataFrame(alertas)
    nivel_counts = df["nivel"].value_counts().reset_index()
    nivel_counts.columns = ["nivel", "contagem"]

    order = ["emergencia", "alerta", "atencao", "informativo"]
    nivel_counts["nivel"] = pd.Categorical(nivel_counts["nivel"], categories=order, ordered=True)
    nivel_counts = nivel_counts.sort_values("nivel")

    colors = {"emergencia": "darkred", "alerta": "red", "atencao": "orange", "informativo": "blue"}
    fig = px.bar(
        nivel_counts,
        x="nivel",
        y="contagem",
        color="nivel",
        color_discrete_map=colors,
        title="Alertas por Nível",
        labels={"nivel": "Nível", "contagem": "Total"},
    )
    fig.update_layout(showlegend=False)
    return fig


def focos_timeline(focos: list[dict]) -> go.Figure:
    """Timeline de focos nas últimas 72h."""
    df = pd.DataFrame(focos)
    if df.empty or "data_hora" not in df.columns:
        return go.Figure()

    df["data_hora"] = pd.to_datetime(df["data_hora"], errors="coerce")
    df = df.dropna(subset=["data_hora"])
    df = df.sort_values("data_hora")

    fig = px.scatter(
        df,
        x="data_hora",
        y="severidade",
        color="severidade",
        size="confianca",
        hover_data=["municipio", "sensor", "frp"],
        title="Focos por Data/Hora",
        labels={"data_hora": "Data/Hora", "severidade": "Severidade"},
        color_discrete_map={"critica": "darkred", "alta": "red", "media": "orange", "baixa": "green"},
    )
    fig.update_layout(height=300)
    return fig


# ── Páginas ────────────────────────────────────────────────────────────────

def page_overview():
    """Página principal: visão geral com mapa e métricas."""
    st.title("🔥 Monitoramento de Queimadas — Ceará")
    st.caption(f"Atualizado: {datetime.now(timezone.utc).strftime('%d/%m/%Y %H:%M:%S')} UTC")

    # ── Sidebar ──
    dias = st.sidebar.slider("Janela de tempo (dias)", 1, 7, 3)
    horas_frente = st.sidebar.slider("Previsão (horas)", 1, 72, 6)

    with st.sidebar.expander("Filtros", expanded=False):
        severidade_filter = st.selectbox(
            "Severidade",
            ["Todas", "critica", "alta", "media", "baixa"],
            index=0,
        )

    if st.sidebar.button("🔄 Atualizar dados", type="primary"):
        st.cache_data.clear()
        st.rerun()

    # ── Fetch data ──
    focos_data = fetch_focos(dias=dias, severidade=severidade_filter if severidade_filter != "Todas" else None)
    clima_data = fetch_clima()
    alertas_data = fetch_alertas(horas=48, dias=dias)
    status_data = fetch_status()
    risco_data = fetch_risco(horas_frente=horas_frente)

    focos = focos_data.get("focos", [])
    clima = clima_data.get("municipios", [])
    alertas = alertas_data.get("alertas", [])
    riscos = risco_data.get("riscos", [])

    # ── Métricas totais ──
    cols = st.columns(4)
    with cols[0]:
        st.metric("Focos Ativos", len(focos))
    with cols[1]:
        criticos = sum(1 for f in focos if f.get("severidade") == "critica")
        st.metric("Críticos", criticos, delta_color="inverse")
    with cols[2]:
        alertas_total = len(alertas)
        alertas_emergencia = sum(1 for a in alertas if a.get("nivel") == "emergencia")
        st.metric("Alertas", alertas_total, delta=alertas_emergencia if alertas_emergencia else None)
    with cols[3]:
        risco_alto = sum(1 for r in riscos if r.get("classificacao") in ("critico", "alto"))
        st.metric("Municípios em Risco", f"{risco_alto}/{len(riscos)}" if riscos else "N/D")

    # ── Mapa principal ──
    st.subheader("🗺️ Mapa de Focos de Queimada")
    if focos:
        m = build_foco_map(focos)
        st_folium(m, width=None, height=500, returned_objects=[])
    else:
        st.info("Nenhum foco ativo no período selecionado. (Período chuvoso no Ceará.)")

    # ── Mapa de Risco ──
    if riscos:
        st.subheader("📊 Mapa de Risco por Município")
        cols_risk = st.columns([2, 1])

        with cols_risk[0]:
            m_risk = build_risk_map(riscos)
            st_folium(m_risk, width=None, height=400, returned_objects=[])

        with cols_risk[1]:
            st.caption("**Top 5 risco**")
            for r in riscos[:5]:
                emoji = {"critico": "🔴", "alto": "🟠", "medio": "🟡", "baixo": "🟢"}.get(r["classificacao"], "⚪")
                st.markdown(f"{emoji} **{r['municipio']}**: {r['indice_risco']:.1%}")
    else:
        st.info("Previsão de risco não disponível (API de inovação offline ou sem dados).")

    # ── Gráficos ──
    st.subheader("📈 Análise")
    col1, col2 = st.columns(2)

    with col1:
        fig_focos = focus_chart(focos)
        if fig_focos.data:
            st.plotly_chart(fig_focos, use_container_width=True)

    with col2:
        fig_alertas = alertas_chart(alertas)
        if fig_alertas.data:
            st.plotly_chart(fig_alertas, use_container_width=True)

    # ── Timeline ──
    fig_timeline = focos_timeline(focos)
    if fig_timeline.data:
        st.plotly_chart(fig_timeline, use_container_width=True)

    # ── Status das fontes ──
    with st.expander("📡 Status das Fontes de Dados", expanded=False):
        col_a, col_b, col_c, col_d = st.columns(4)
        sources = {
            "NASA FIRMS": status_data.get("nasa_firms", {}).get("status", "desconhecido"),
            "Open-Meteo": status_data.get("open_meteo", {}).get("status", "desconhecido"),
            "Nominatim": status_data.get("nominatim", {}).get("status", "desconhecido"),
            "Cache": "ok" if status_data.get("cache_focos", 0) > 0 else "vazio",
        }
        for col, (name, status) in zip([col_a, col_b, col_c, col_d], sources.items()):
            icon = "✅" if status == "ok" else "❌"
            col.metric(name, f"{icon} {status}")


def page_focos():
    """Tabela detalhada de focos."""
    st.title("🔍 Detalhamento de Focos")

    dias = st.slider("Dias", 1, 7, 3)
    severidade_filter = st.selectbox("Filtrar por severidade", ["Todas", "critica", "alta", "media", "baixa"])

    focos_data = fetch_focos(
        dias=dias,
        severidade=severidade_filter if severidade_filter != "Todas" else None,
    )
    focos = focos_data.get("focos", [])

    st.caption(f"Total: {len(focos)} focos | Atualizado em: {focos_data.get('atualizado_em', 'N/D')}")

    st.metric("Total de focos", len(focos))

    if not focos:
        st.info("Nenhum foco detectado no período.")
        return

    # Tabela
    rows = []
    for f in focos:
        rows.append({
            "Município": f.get("municipio", "?"),
            "Severidade": f.get("severidade", "?"),
            "Confiança": f"{f.get('confianca', 0):.0f}%",
            "FRP": f.get("frp", "N/A"),
            "Sensor": f.get("sensor", ""),
            "Satélite": f.get("satelite", ""),
            "Data/Hora": f.get("data_hora", ""),
            "Latitude": f"{f.get('latitude', f.get('lat', 0)):.4f}",
            "Longitude": f"{f.get('longitude', f.get('lon', 0)):.4f}",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Botão exportar CSV
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Exportar CSV",
        data=csv,
        file_name=f"focos_queimadas_ceara_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )


def page_clima():
    """Dados climáticos por município."""
    st.title("🌦️ Condições Climáticas")
    clima_data = fetch_clima()
    municipios = clima_data.get("municipios", [])

    st.caption(f"Total: {clima_data.get('total', 0)} municípios")

    if not municipios:
        st.info("Dados climáticos indisponíveis.")
        return

    rows = []
    for m in municipios:
        rows.append({
            "Município": m.get("municipio", m.get("nome", "?")),
            "Temp (°C)": m.get("temperatura_2m", m.get("temperature", "N/A")),
            "Umidade (%)": m.get("umidade_relativa", m.get("humidity", "N/A")),
            "Vento (km/h)": m.get("vento_10m", m.get("wind_speed", "N/A")),
            "Precipitação": m.get("precipitacao", m.get("precipitation", "N/A")),
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Mapa de temperatura
    if "Latitude" not in df.columns and "latitude" not in df.columns:
        # Tenta extrair lat/lon
        m_map = folium.Map(location=(-5.0, -39.5), zoom_start=7)
        for m in municipios:
            lat = m.get("latitude") or m.get("lat")
            lon = m.get("longitude") or m.get("lon")
            temp = m.get("temperatura_2m", m.get("temperature", "N/A"))
            nome = m.get("municipio", m.get("nome", "?"))
            if lat and lon:
                popup = f"<b>{nome}</b><br>Temp: {temp}°C"
                folium.Marker(
                    [lat, lon],
                    popup=popup,
                    tooltip=f"{nome}: {temp}°C",
                    icon=folium.Icon(color="blue", icon="cloud"),
                ).add_to(m_map)
        st_folium(m_map, width=None, height=400, returned_objects=[])


def page_alertas():
    """Alertas gerados automaticamente."""
    st.title("🚨 Alertas de Queimadas")

    col1, col2 = st.columns(2)
    with col1:
        horas = st.number_input("Janela (horas)", 6, 168, 48, step=6)
    with col2:
        nivel_filter = st.selectbox("Nível", ["Todos", "informativo", "atencao", "alerta", "emergencia"])

    alertas_data = fetch_alertas(horas=horas, dias=3)
    alertas = alertas_data.get("alertas", [])

    if nivel_filter != "Todos":
        alertas = [a for a in alertas if a.get("nivel") == nivel_filter]

    st.metric("Total de Alertas", len(alertas))

    if not alertas:
        st.info("Nenhum alerta gerado no período.")
        return

    # Cards de alerta
    for a in alertas:
        nivel = a.get("nivel", "informativo")
        emoji = {"emergencia": "🔴", "alerta": "🟠", "atencao": "🟡", "informativo": "🔵"}.get(nivel, "⚪")
        municipio = a.get("municipio", a.get("regiao", "?"))
        mensagem = a.get("mensagem", a.get("descricao", ""))
        acao = a.get("acao_recomendada", a.get("acao", ""))

        with st.expander(f"{emoji} [{nivel.upper()}] {municipio}", expanded=nivel in ("emergencia", "alerta")):
            st.markdown(f"**Mensagem:** {mensagem}")
            if acao:
                st.markdown(f"**Ação recomendada:** {acao}")
            st.caption(f"Gerado em: {a.get('data_geracao', a.get('timestamp', 'N/A'))}")


def page_risk():
    """Previsão de risco por município."""
    st.title("🎯 Previsão de Risco — NeKo-PIGNN")

    horas_frente = st.slider("Horas à frente para previsão", 1, 72, 6)
    risco_data = fetch_risco(horas_frente=horas_frente)
    riscos = risco_data.get("riscos", [])

    if not riscos:
        st.warning(
            "Previsão de risco indisponível. "
            "Verifique se a API FastAPI está rodando e o modelo está carregado."
        )
        return

    st.metric("Municípios analisados", len(riscos))

    # Tabela de risco
    rows = []
    for r in riscos:
        rows.append({
            "Município": r["municipio"],
            "Risco": f"{r['indice_risco']:.1%}",
            "Classificação": r["classificacao"].upper(),
            "FRP Previsto": f"{r['frp_previsto']:.3f}",
            "Rothermel": f"{r['rothermel_score']:.1%}",
            "Koopman": r["componentes"]["modelo_koopman"],
            "Persistência": r["componentes"]["persistencia_focos"],
        })

    df = pd.DataFrame(rows)

    # Colorir classificação
    def color_risk(val):
        colors = {"BAIXO": "green", "MÉDIO": "orange", "ALTO": "red", "CRITICO": "darkred"}
        return f"color: {colors.get(val, 'black')}; font-weight: bold"

    st.dataframe(
        df.style.applymap(color_risk, subset=["Classificação"]),
        use_container_width=True,
        hide_index=True,
    )

    # Gráfico de barras
    fig = px.bar(
        df.sort_values("Risco", ascending=True),
        x="Risco",
        y="Município",
        color="Classificação",
        color_discrete_map={
            "BAIXO": "green", "MÉDIO": "orange", "ALTO": "red", "CRITICO": "darkred",
        },
        title=f"Risco por Município (próximas {horas_frente}h)",
        orientation="h",
    )
    fig.update_layout(height=max(400, len(riscos) * 28))
    st.plotly_chart(fig, use_container_width=True)

    # Breakdown componentes
    st.subheader("📊 Componentes do Índice de Risco")
    comp_data = []
    for r in riscos:
        comp_data.append({
            "Município": r["municipio"],
            **r["componentes"],
        })
    df_comp = pd.DataFrame(comp_data)
    st.dataframe(df_comp, use_container_width=True, hide_index=True)


def page_status():
    """Status do sistema e fontes de dados."""
    st.title("📡 Status do Sistema")

    status = fetch_status()

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Fontes de Dados")
        for source in ["nasa_firms", "open_meteo", "nominatim"]:
            s = status.get(source, {})
            icon = "✅" if s.get("status") == "ok" else "❌"
            st.markdown(f"{icon} **{source}**: {s.get('status', 'desconhecido')} (HTTP {s.get('http', 'N/A')})")

    with col2:
        st.subheader("Cache")
        st.metric("Focos em cache", status.get("cache_focos", 0))
        st.metric("Última atualização", status.get("cache_atualizado", "Nunca"))

    st.subheader("Modelos")
    st.json(status.get("deepseek_configurado", False))
    st.markdown(f"**DeepSeek configurado:** {'✅' if status.get('deepseek_configurado') else '❌'}")
    st.markdown(f"**Modelo:** {status.get('deepseek_model', 'N/A')}")

    # Raw status
    with st.expander("Status completo (JSON)", expanded=False):
        st.json(status)


def page_sobre():
    """Sobre o dashboard."""
    st.title("ℹ️ Sobre")
    st.markdown("""
    ## Dashboard de Monitoramento de Queimadas — Ceará

    Este dashboard integra dados de múltiplas fontes para monitoramento em tempo real de queimadas no estado do Ceará.

    ### Fontes de Dados
    - **NASA FIRMS**: Focos ativos via satélites VIIRS (SNPP, NOAA-20) e MODIS
    - **Open-Meteo**: Condições climáticas atuais e previsão
    - **Nominatim (OSM)**: Geocodificação reversa (coordenadas → município)

    ### Modelo de Previsão
    - **NeKo-PIGNN**: Neural Koopman Operator + Physics-Informed GNN
    - Koopman Determinístico para evolução temporal
    - GNN para propagação espacial entre municípios
    - Regularização física de Rothermel

    ### Stack
    - **Backend**: FastAPI + LangChain/LangGraph + PyTorch
    - **Dashboard**: Streamlit + Folium + Plotly
    - **Dados**: NASA FIRMS (CSV público), Open-Meteo (gratuito)
    - **Coleta**: Dados reais ao vivo (sem banco de dados)

    ---
    **Gêmeo Digital do Ceará** | [Repositório](https://github.com/naubergois/ceara-queimadas)
    """)


# ── Navegação ──────────────────────────────────────────────────────────────

PAGES = {
    "Visão Geral": page_overview,
    "Focos": page_focos,
    "Clima": page_clima,
    "Alertas": page_alertas,
    "Previsão de Risco": page_risk,
    "Status": page_status,
    "Sobre": page_sobre,
}


def main():
    st.set_page_config(
        page_title="Queimadas Ceará — Dashboard",
        page_icon="🔥",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.sidebar.image(
        "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9a/Brasão_do_Ceará.svg/200px-Brasão_do_Ceará.svg.png",
        width=80,
    )
    st.sidebar.title("🔥 Queimadas CE")
    st.sidebar.caption("Gêmeo Digital — Monitoramento")

    page_name = st.sidebar.radio("Navegação", list(PAGES.keys()), index=0)
    st.sidebar.markdown("---")
    st.sidebar.caption(f"API: {API_BASE}")
    st.sidebar.caption(f"Atualização: 5-10 min")

    page_func = PAGES[page_name]
    page_func()


if __name__ == "__main__":
    main()
