"""
Controle de Validade e Gestão de Estoque - Protótipo
Projeto Integrador em Ciência de Dados I - UFMS Digital
Autor: Marcelo Neiva Henriques

Como rodar:
    pip install streamlit pandas requests
    streamlit run app.py
"""

import io
from datetime import date, datetime

import pandas as pd
import requests
import streamlit as st

st.set_page_config(
    page_title="Controle de Validade - Mercado",
    page_icon="📦",
    layout="wide",
)

# ---------------------------------------------------------
# Conexão com a planilha via Google Apps Script (Web App)
# ---------------------------------------------------------
URL_APPS_SCRIPT = "https://script.google.com/macros/s/AKfycbyQdF9LYCNK6b98KKk9LELRADqLKH6cWv-pcQ0kg6kUP_m1uV3DNSL1Lqr-Bh0inSng/exec"

COLUNAS_LOTES = ["ID", "Produto", "Categoria", "Data de entrada", "Data de validade", "Quantidade"]
COLUNAS_MOVIMENTOS = ["Data", "ID do lote", "Produto", "Tipo", "Quantidade", "Motivo"]
COLUNAS_TABELA = ["Produto", "Categoria", "Data de entrada", "Data de validade", "Dias restantes", "Quantidade", "Status"]
CATEGORIAS = ["Laticínios", "Mercearia", "Bebidas", "Enlatados", "Hortifruti", "Padaria", "Outros"]
MOTIVOS = ["Vencido", "Avariado", "Outro"]


def carregar_lotes():
    resposta = requests.get(URL_APPS_SCRIPT, timeout=15)
    resposta.raise_for_status()
    registros = resposta.json()
    if not registros:
        return pd.DataFrame(columns=COLUNAS_LOTES)
    df = pd.DataFrame(registros)
    if "ID" not in df.columns:
        df["ID"] = ""
    df["ID"] = df["ID"].astype(str)
    df["Data de entrada"] = pd.to_datetime(df["Data de entrada"])
    df["Data de validade"] = pd.to_datetime(df["Data de validade"])
    df["Quantidade"] = df["Quantidade"].astype(int)
    return df


def carregar_movimentos():
    resposta = requests.get(URL_APPS_SCRIPT, params={"acao": "movimentos"}, timeout=15)
    resposta.raise_for_status()
    registros = resposta.json()
    if not registros:
        return pd.DataFrame(columns=COLUNAS_MOVIMENTOS)
    df = pd.DataFrame(registros)
    df["Data"] = pd.to_datetime(df["Data"])
    df["Quantidade"] = df["Quantidade"].astype(int)
    df["Motivo"] = df["Motivo"].fillna("")
    return df


def salvar_lote(nome, categoria, data_entrada, data_validade, quantidade):
    corpo = {
        "produto": nome,
        "categoria": categoria,
        "data_entrada": data_entrada.strftime("%Y-%m-%d"),
        "data_validade": data_validade.strftime("%Y-%m-%d"),
        "quantidade": quantidade,
    }
    resposta = requests.post(URL_APPS_SCRIPT, json=corpo, timeout=15)
    resposta.raise_for_status()
    return resposta.json()


def registrar_baixa(id_lote, tipo, quantidade, motivo):
    corpo = {
        "acao": "baixa",
        "id": id_lote,
        "tipo": tipo,
        "quantidade": quantidade,
        "motivo": motivo,
    }
    resposta = requests.post(URL_APPS_SCRIPT, json=corpo, timeout=15)
    resposta.raise_for_status()
    return resposta.json()


# ---------------------------------------------------------
# Funções de apoio
# ---------------------------------------------------------
def status_alerta(dias):
    if dias <= 0:
        return "🔴 Vencido"
    elif dias <= 3:
        return "🔴 Crítico"
    elif dias <= 7:
        return "🟡 Atenção"
    return "🟢 Ok"


def cor_status(status):
    if "🔴" in status:
        return "background-color: #f5c6cb; color: #1a1a1a"
    elif "🟡" in status:
        return "background-color: #ffe8a1; color: #1a1a1a"
    return "background-color: #c3e6cb; color: #1a1a1a"


def preparar_lotes(df):
    df = df.copy()
    if df.empty:
        df["Dias restantes"] = pd.Series(dtype="int64")
        df["Status"] = pd.Series(dtype="object")
        return df
    hoje = pd.Timestamp(date.today())
    df["Dias restantes"] = (df["Data de validade"] - hoje).dt.days
    df["Status"] = df["Dias restantes"].apply(status_alerta)
    return df


def formatar_datas(df):
    exibir = df.copy()
    exibir["Data de entrada"] = exibir["Data de entrada"].dt.strftime("%d/%m/%Y")
    exibir["Data de validade"] = exibir["Data de validade"].dt.strftime("%d/%m/%Y")
    return exibir


def mostrar_tabela(df):
    if df.empty:
        st.info("Nenhum produto nesta visão.")
        return
    exibir = formatar_datas(df)[COLUNAS_TABELA]
    st.dataframe(
        exibir.style.apply(lambda row: [cor_status(row["Status"])] * len(row), axis=1),
        use_container_width=True,
        hide_index=True,
    )


def formulario_baixa(df, chave):
    if df.empty:
        st.info("Nenhum lote disponível para baixa nesta visão.")
        return

    rotulos = {
        f"{r['Produto']} | validade {r['Data de validade']:%d/%m/%Y} | restam {r['Quantidade']} | lote {r['ID']}": idx
        for idx, r in df.iterrows()
    }
    escolha = st.selectbox("Lote", list(rotulos.keys()), key=f"lote_{chave}")
    lote = df.loc[rotulos[escolha]]

    tipo = st.radio("Tipo de saída", ["Venda", "Descarte"], horizontal=True, key=f"tipo_{chave}")
    quantidade = st.number_input(
        "Quantidade",
        min_value=1,
        max_value=int(lote["Quantidade"]),
        value=1,
        step=1,
        key=f"qtd_{chave}",
    )

    motivo = ""
    if tipo == "Descarte":
        motivo = st.selectbox("Motivo do descarte", MOTIVOS, key=f"motivo_{chave}")

    if st.button("Dar baixa", key=f"botao_{chave}", type="primary"):
        resultado = registrar_baixa(lote["ID"], tipo.lower(), int(quantidade), motivo)
        if resultado.get("status") == "ok":
            st.session_state["mensagem"] = (
                f"Baixa registrada: {int(quantidade)} unidade(s) de {lote['Produto']} ({tipo.lower()})."
            )
            st.rerun()
        else:
            st.error(resultado.get("mensagem", "Não foi possível registrar a baixa."))


def aba_descartes(movimentos):
    descartes = movimentos[movimentos["Tipo"] == "descarte"] if not movimentos.empty else movimentos
    if descartes.empty:
        st.info("Nenhum descarte registrado ainda.")
        return

    col1, col2 = st.columns(2)
    motivos = col1.multiselect("Motivo", MOTIVOS, default=MOTIVOS, key="filtro_motivo")
    minimo = col2.number_input(
        "Quantidade mínima descartada (por registro)",
        min_value=0,
        value=0,
        step=1,
        key="filtro_qtd",
    )

    filtrado = descartes[descartes["Motivo"].isin(motivos) & (descartes["Quantidade"] >= minimo)]
    if filtrado.empty:
        st.info("Nenhum descarte com esses filtros.")
        return

    exibir = filtrado.copy()
    exibir["Data"] = exibir["Data"].dt.strftime("%d/%m/%Y")
    st.dataframe(
        exibir[["Data", "Produto", "Quantidade", "Motivo"]],
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("**Total descartado por produto**")
    total = (
        filtrado.groupby("Produto", as_index=False)["Quantidade"]
        .sum()
        .sort_values("Quantidade", ascending=False)
    )
    st.dataframe(total, use_container_width=True, hide_index=True)


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

if "mensagem" in st.session_state:
    st.success(st.session_state.pop("mensagem"))

# ---------------------------------------------------------
# Formulário de cadastro de lote
# ---------------------------------------------------------
with st.expander("➕ Cadastrar novo lote", expanded=True):
    with st.form("form_lote", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Nome do produto")
            categoria = st.selectbox("Categoria", CATEGORIAS)
            quantidade = st.number_input("Quantidade em estoque", min_value=1, step=1)
        with col2:
            data_entrada = st.date_input("Data de entrada", value=date.today(), format="DD/MM/YYYY")
            data_validade = st.date_input("Data de validade", value=date.today(), format="DD/MM/YYYY")

        enviado = st.form_submit_button("Salvar lote", use_container_width=True)

        if enviado:
            if not nome.strip():
                st.warning("Informe o nome do produto antes de salvar.")
            elif data_validade < data_entrada:
                st.warning("A data de validade não pode ser anterior à data de entrada.")
            else:
                salvar_lote(nome.strip(), categoria, data_entrada, data_validade, int(quantidade))
                st.session_state["mensagem"] = f"Lote de '{nome.strip()}' cadastrado com sucesso!"
                st.rerun()

st.divider()

# ---------------------------------------------------------
# Carregamento e separação das visões
# ---------------------------------------------------------
try:
    lotes = preparar_lotes(carregar_lotes())
    movimentos = carregar_movimentos()
except (requests.RequestException, ValueError) as erro:
    st.error("Não foi possível ler a planilha. Verifique a URL do Apps Script e o acesso da implantação.")
    st.caption(f"Detalhe técnico: {erro}")
    st.stop()

com_estoque = lotes[lotes["Quantidade"] > 0].sort_values("Dias restantes")
vencidos = com_estoque[com_estoque["Dias restantes"] <= 0]
vencendo_3 = com_estoque[(com_estoque["Dias restantes"] >= 1) & (com_estoque["Dias restantes"] <= 3)]

descartes = movimentos[movimentos["Tipo"] == "descarte"] if not movimentos.empty else movimentos
total_descartado = int(descartes["Quantidade"].sum()) if not descartes.empty else 0

# ---------------------------------------------------------
# Painel de indicadores
# ---------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)
col1.metric("Lotes com estoque", len(com_estoque))
col2.metric("🔴 Vencidos", len(vencidos))
col3.metric("🟡 Vencendo em até 3 dias", len(vencendo_3))
col4.metric("Unidades descartadas", total_descartado)

st.divider()

# ---------------------------------------------------------
# Visões
# ---------------------------------------------------------
aba_todos, aba_3dias, aba_vencidos, aba_baixa, aba_desc = st.tabs([
    "Todos os produtos",
    "Vencendo em 3 dias",
    "Produtos vencidos",
    "Dar baixa",
    "Descartes",
])

with aba_todos:
    mostrar_tabela(com_estoque)
    if not com_estoque.empty:
        buffer = io.StringIO()
        formatar_datas(com_estoque)[COLUNAS_TABELA].to_csv(buffer, index=False)
        st.download_button(
            label="⬇️ Exportar produtos (CSV)",
            data=buffer.getvalue(),
            file_name=f"produtos_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

with aba_3dias:
    mostrar_tabela(vencendo_3)

with aba_vencidos:
    mostrar_tabela(vencidos)
    st.markdown("**Dar baixa em produto vencido**")
    formulario_baixa(vencidos, "vencidos")

with aba_baixa:
    st.markdown("Registre uma venda ou um descarte de qualquer lote com estoque.")
    formulario_baixa(com_estoque, "geral")

with aba_desc:
    aba_descartes(movimentos)

st.caption("Protótipo desenvolvido para fins acadêmicos — Projeto Integrador em Ciência de Dados I (UFMS Digital).")
