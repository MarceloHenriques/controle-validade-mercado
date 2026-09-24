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

st.set_page_config(
    page_title="Controle de Validade - Mercado",
    page_icon="📦",
    layout="wide",
)

# ---------------------------------------------------------
# Estado inicial (dados ficam na memória enquanto o app roda)
# ---------------------------------------------------------
if "produtos" not in st.session_state:
    # alguns itens de exemplo, só para já mostrar a tabela funcionando
    st.session_state.produtos = pd.DataFrame([
        {"Produto": "Leite Integral 1L", "Categoria": "Laticínios",
         "Data de entrada": date(2026, 9, 20), "Data de validade": date(2026, 9, 27),
         "Quantidade": 12},
        {"Produto": "Iogurte Natural", "Categoria": "Laticínios",
         "Data de entrada": date(2026, 9, 22), "Data de validade": date(2026, 9, 30),
         "Quantidade": 8},
        {"Produto": "Arroz 5kg", "Categoria": "Mercearia",
         "Data de entrada": date(2026, 8, 1), "Data de validade": date(2026, 12, 15),
         "Quantidade": 20},
    ])

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
        return "background-color: #ffcccc"
    elif "🟡" in status:
        return "background-color: #fff3cd"
    else:
        return "background-color: #d4edda"

# ---------------------------------------------------------
# Cabeçalho
# ---------------------------------------------------------
st.title("📦 Controle de Validade e Estoque")
st.caption("Protótipo do Projeto Integrador em Ciência de Dados I — mercado de bairro")

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
                novo = pd.DataFrame([{
                    "Produto": nome.strip(),
                    "Categoria": categoria,
                    "Data de entrada": data_entrada,
                    "Data de validade": data_validade,
                    "Quantidade": quantidade,
                }])
                st.session_state.produtos = pd.concat(
                    [st.session_state.produtos, novo], ignore_index=True
                )
                st.success(f"Produto '{nome}' cadastrado com sucesso!")

st.divider()

# ---------------------------------------------------------
# Cálculo dos alertas
# ---------------------------------------------------------
df = st.session_state.produtos.copy()
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
