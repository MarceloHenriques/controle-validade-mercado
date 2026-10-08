"""
Controle de Validade e Gestão de Estoque - Protótipo
Projeto Integrador em Ciência de Dados I - UFMS Digital
Autor: Marcelo Neiva Henriques

Como rodar:
    pip install streamlit pandas
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
import io
import requests

st.set_page_config(
    page_title="Controle de Validade - Mercado",
    page_icon="📦",
    layout="wide",
)

# ---------------------------------------------------------
# Conexão com a planilha via Google Apps Script (Web App)
# ---------------------------------------------------------
# Cole aqui o link gerado na etapa "Publicar como App da Web".
URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbyQdF9LYCNK6b98KKk9LELRADqLKH6cWv-pcQ0kg6kUP_m1uV3DNSL1Lqr-Bh0inSng/exec"

COLUNAS = ["Produto", "Categoria", "Data de entrada", "Data de validade", "Quantidade"]

def carregar_produtos():
    resposta = requests.get(URL_APPS_SCRIPT, timeout=15)
    resposta.raise_for_status()
    registros = resposta.json()
    if not registros:
        return pd.DataFrame(columns=COLUNAS)
    df = pd.DataFrame(registros)
    df["Data de entrada"] = pd.to_datetime(df["Data de entrada"]).dt.date
    df["Data de validade"] = pd.to_datetime(df["Data de validade"]).dt.date
    df["Quantidade"] = df["Quantidade"].astype(int)
    return df

def salvar_produto(nome, categoria, data_entrada, data_validade, quantidade):
    corpo = {
        "produto": nome,
        "categoria": categoria,
        "data_entrada": data_entrada.strftime("%Y-%m-%d"),
        "data_validade": data_validade.strftime("%Y-%m-%d"),
        "quantidade": quantidade,
    }
    resposta = requests.post(URL_APPS_SCRIPT, json=corpo, timeout=15)
    resposta.raise_for_status()

CATEGORIAS = ["Laticínios", "Mercearia", "Bebidas", "Enlatados", "Hortifruti", "Padaria", "Outros"]

# ---------------------------------------------------------
# Funções de apoio
# ---------------------------------------------------------
def dias_restantes(data_validade):
    return (data_validade - date.today()).days

def status_alerta(dias):
    if dias <= 3:
        return "🔴 Crítico"
    elif dias <= 7:
        return "🟡 Atenção"
    else:
        return "🟢 Ok"

def cor_status(status):
    if "🔴" in status:
        return "background-color: #f5c6cb; color: #1a1a1a"
    elif "🟡" in status:
        return "background-color: #ffe8a1; color: #1a1a1a"
    else:
        return "background-color: #c3e6cb; color: #1a1a1a"

# ---------------------------------------------------------
# Cabeçalho
# ---------------------------------------------------------
st.markdown(
    """
    <div style="
        background: linear-gradient(90deg, #0f4c75, #3282b8);
        padding: 28px 32px;
        border-radius: 12px;
        margin-bottom: 24px;
    ">
        <h1 style="color: white; margin: 0; font-size: 34px;">📦 Controle de Validade e Estoque</h1>
        <p style="color: #dceeff; margin: 6px 0 0 0; font-size: 16px;">
            Protótipo do Projeto Integrador em Ciência de Dados I — mercado de bairro
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# Formulário de cadastro
# ---------------------------------------------------------
with st.expander("➕ Cadastrar novo produto", expanded=True):
    with st.form("form_produto", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Nome do produto")
            categoria = st.selectbox("Categoria", CATEGORIAS)
            quantidade = st.number_input("Quantidade em estoque", min_value=0, step=1)
        with col2:
            data_entrada = st.date_input("Data de entrada", value=date.today())
            data_validade = st.date_input("Data de validade", value=date.today())

        enviado = st.form_submit_button("Salvar produto", use_container_width=True)

        if enviado:
            if not nome.strip():
                st.warning("Informe o nome do produto antes de salvar.")
            elif data_validade < data_entrada:
                st.warning("A data de validade não pode ser anterior à data de entrada.")
            else:
                salvar_produto(nome.strip(), categoria, data_entrada, data_validade, quantidade)
                st.success(f"Produto '{nome}' cadastrado com sucesso!")
                st.rerun()

st.divider()

# ---------------------------------------------------------
# Cálculo dos alertas
# ---------------------------------------------------------
df = carregar_produtos()
df["Dias restantes"] = df["Data de validade"].apply(dias_restantes)
df["Status"] = df["Dias restantes"].apply(status_alerta)
df = df.sort_values("Dias restantes")

# ---------------------------------------------------------
# Painel de indicadores
# ---------------------------------------------------------
total = len(df)
criticos = (df["Dias restantes"] <= 3).sum()
atencao = ((df["Dias restantes"] > 3) & (df["Dias restantes"] <= 7)).sum()

col1, col2, col3 = st.columns(3)
col1.metric("Total de produtos cadastrados", total)
col2.metric("🔴 Em risco crítico (≤ 3 dias)", int(criticos))
col3.metric("🟡 Em atenção (4 a 7 dias)", int(atencao))

st.divider()

# ---------------------------------------------------------
# Filtro rápido
# ---------------------------------------------------------
filtro = st.radio(
    "Filtrar por status:",
    ["Todos", "🔴 Crítico", "🟡 Atenção", "🟢 Ok"],
    horizontal=True,
)
if filtro != "Todos":
    df_exibir = df[df["Status"] == filtro]
else:
    df_exibir = df

# ---------------------------------------------------------
# Tabela com destaque de cor
# ---------------------------------------------------------
st.subheader("📊 Produtos em estoque")

if df_exibir.empty:
    st.info("Nenhum produto encontrado para esse filtro.")
else:
    df_mostrar = df_exibir[[
        "Produto", "Categoria", "Data de entrada", "Data de validade",
        "Dias restantes", "Quantidade", "Status"
    ]]
    st.dataframe(
        df_mostrar.style.apply(
            lambda row: [cor_status(row["Status"])] * len(row), axis=1
        ),
        use_container_width=True,
        hide_index=True,
    )

# ---------------------------------------------------------
# Exportar produtos em risco (CSV)
# ---------------------------------------------------------
df_risco = df[df["Dias restantes"] <= 7]
if not df_risco.empty:
    csv_buffer = io.StringIO()
    df_risco.to_csv(csv_buffer, index=False)
    st.download_button(
        label="⬇️ Exportar produtos em risco (CSV)",
        data=csv_buffer.getvalue(),
        file_name=f"produtos_em_risco_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        use_container_width=True,
    )

st.caption("Protótipo desenvolvido para fins acadêmicos — Projeto Integrador em Ciência de Dados I (UFMS Digital).")
