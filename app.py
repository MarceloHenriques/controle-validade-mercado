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
from html import escape

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
COLUNAS_EXPORTACAO = ["Produto", "Categoria", "Data de entrada", "Data de validade", "Dias restantes", "Quantidade", "Status"]
CATEGORIAS = ["Laticínios", "Mercearia", "Bebidas", "Enlatados", "Hortifruti", "Padaria", "Outros"]
MOTIVOS = ["Vencido", "Avariado", "Outro"]
CAMPOS_CADASTRO = ["nome", "categoria", "quantidade", "data_entrada", "data_validade"]


def converter_data(serie):
    # Deixa todas as datas no mesmo formato, sem fuso horário
    return pd.to_datetime(serie, errors="coerce", utc=True).dt.tz_localize(None).dt.normalize()


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
    df["Data de entrada"] = converter_data(df["Data de entrada"])
    df["Data de validade"] = converter_data(df["Data de validade"])
    df["Quantidade"] = df["Quantidade"].astype(int)
    return df


def carregar_movimentos():
    resposta = requests.get(URL_APPS_SCRIPT, params={"acao": "movimentos"}, timeout=15)
    resposta.raise_for_status()
    registros = resposta.json()
    if not registros:
        return pd.DataFrame(columns=COLUNAS_MOVIMENTOS)
    df = pd.DataFrame(registros)
    df["Data"] = converter_data(df["Data"])
    df["Quantidade"] = df["Quantidade"].astype(int)
    df["Motivo"] = df["Motivo"].fillna("")
    return df


def enviar(corpo):
    # Envia qualquer ação para a planilha e devolve a resposta como dicionário
    try:
        resposta = requests.post(URL_APPS_SCRIPT, json=corpo, timeout=15)
        resposta.raise_for_status()
        return resposta.json()
    except (requests.RequestException, ValueError) as erro:
        return {"status": "erro", "mensagem": f"Falha ao falar com a planilha: {erro}"}


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


def cor_fundo(status):
    if "🔴" in status:
        return "#f5c6cb"
    elif "🟡" in status:
        return "#ffe8a1"
    return "#c3e6cb"


def texto_prazo(dias):
    if dias < 0:
        return f"vencido há {-dias} dia(s)"
    if dias == 0:
        return "vence hoje"
    return f"faltam {dias} dia(s)"


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


# ---------------------------------------------------------
# Cadastro de lote (sem formulário: Enter não salva)
# ---------------------------------------------------------
def salvar_lote_callback():
    nome = (st.session_state.get("nome") or "").strip()
    categoria = st.session_state.get("categoria")
    quantidade = st.session_state.get("quantidade")
    entrada = st.session_state.get("data_entrada")
    validade = st.session_state.get("data_validade")

    faltando = []
    if not nome:
        faltando.append("Nome do produto")
    if categoria is None:
        faltando.append("Categoria")
    if quantidade is None:
        faltando.append("Quantidade em estoque")
    if faltando:
        st.session_state["erro"] = " ".join(f"Favor preencher o campo {campo}." for campo in faltando)
        return

    if validade < entrada:
        st.session_state["erro"] = "A data de validade não pode ser anterior à data de entrada."
        return

    resultado = enviar({
        "produto": nome,
        "categoria": categoria,
        "data_entrada": entrada.strftime("%Y-%m-%d"),
        "data_validade": validade.strftime("%Y-%m-%d"),
        "quantidade": int(quantidade),
    })

    if resultado.get("status") == "ok":
        st.session_state["mensagem"] = f"Lote de '{nome}' cadastrado com sucesso!"
        for campo in CAMPOS_CADASTRO:
            st.session_state.pop(campo, None)
    else:
        st.session_state["erro"] = resultado.get("mensagem", "Não foi possível salvar o lote.")


# ---------------------------------------------------------
# Lista de lotes com ações por linha
# ---------------------------------------------------------
def mostrar_lotes(df, contexto):
    if df.empty:
        st.info("Nenhum produto nesta visão.")
        return

    for _, lote in df.iterrows():
        id_lote = str(lote["ID"])
        chave = f"{contexto}_{id_lote}"
        dias = int(lote["Dias restantes"])
        qtd_lote = int(lote["Quantidade"])

        info, col_baixa, col_editar, col_excluir = st.columns([8, 1.3, 1, 1.2])

        linha_html = (
            f'<div style="background:{cor_fundo(lote["Status"])}; color:#1a1a1a; '
            f'padding:8px 12px; border-radius:8px; margin-bottom:6px;">'
            f'<b>{escape(str(lote["Produto"]))}</b> · {escape(str(lote["Categoria"]))} · '
            f'entrada {lote["Data de entrada"]:%d/%m/%Y} · '
            f'validade {lote["Data de validade"]:%d/%m/%Y} · '
            f'{texto_prazo(dias)} · {qtd_lote} un. · {lote["Status"]}'
            f'</div>'
        )
        info.markdown(linha_html, unsafe_allow_html=True)

        # Dar baixa: venda ou descarte, com quantidade e motivo
        with col_baixa.popover("Dar baixa"):
            tipo = st.radio("Tipo de saída", ["Venda", "Descarte"], horizontal=True, key=f"tipo_{chave}")
            qtd = st.number_input(
                "Quantidade",
                min_value=1,
                max_value=qtd_lote,
                value=1,
                step=1,
                key=f"qtd_{chave}",
            )
            motivo = ""
            if tipo == "Descarte":
                motivo = st.selectbox("Motivo do descarte", MOTIVOS, key=f"motivo_{chave}")

            if st.button("Registrar baixa", key=f"ok_baixa_{chave}", type="primary"):
                if tipo == "Descarte" and not motivo:
                    st.error("Escolha o motivo do descarte.")
                else:
                    resultado = enviar({
                        "acao": "baixa",
                        "id": id_lote,
                        "tipo": tipo.lower(),
                        "quantidade": int(qtd),
                        "motivo": motivo,
                    })
                    if resultado.get("status") == "ok":
                        st.session_state["mensagem"] = (
                            f"Baixa registrada: {int(qtd)} unidade(s) de {lote['Produto']} ({tipo.lower()})."
                        )
                        st.rerun()
                    else:
                        st.error(resultado.get("mensagem", "Não foi possível registrar a baixa."))

        # Editar: altera os dados do lote
        with col_editar.popover("Editar"):
            nome_e = st.text_input("Produto", value=str(lote["Produto"]), key=f"enome_{chave}")
            cat_idx = CATEGORIAS.index(lote["Categoria"]) if lote["Categoria"] in CATEGORIAS else None
            cat_e = st.selectbox(
                "Categoria", CATEGORIAS, index=cat_idx, placeholder="Selecione uma categoria", key=f"ecat_{chave}"
            )
            qtd_e = st.number_input(
                "Quantidade em estoque", min_value=1, value=qtd_lote, step=1, key=f"eqtd_{chave}"
            )
            ent_e = st.date_input(
                "Data de entrada", value=lote["Data de entrada"].date(), format="DD/MM/YYYY", key=f"eent_{chave}"
            )
            val_e = st.date_input(
                "Data de validade", value=lote["Data de validade"].date(), format="DD/MM/YYYY", key=f"eval_{chave}"
            )

            if st.button("Salvar alterações", key=f"ok_edit_{chave}", type="primary"):
                if not nome_e.strip() or cat_e is None:
                    st.error("Preencha o nome e a categoria.")
                elif val_e < ent_e:
                    st.error("A data de validade não pode ser anterior à data de entrada.")
                else:
                    resultado = enviar({
                        "acao": "editar",
                        "id": id_lote,
                        "produto": nome_e.strip(),
                        "categoria": cat_e,
                        "data_entrada": ent_e.strftime("%Y-%m-%d"),
                        "data_validade": val_e.strftime("%Y-%m-%d"),
                        "quantidade": int(qtd_e),
                    })
                    if resultado.get("status") == "ok":
                        st.session_state["mensagem"] = "Lote atualizado com sucesso."
                        st.rerun()
                    else:
                        st.error(resultado.get("mensagem", "Não foi possível salvar as alterações."))

        # Excluir: apaga o lote da planilha, com confirmação
        with col_excluir.popover("Excluir"):
            st.warning("Apagar este lote da planilha? Não tem como desfazer.")
            if st.button("Confirmar exclusão", key=f"ok_del_{chave}", type="primary"):
                resultado = enviar({"acao": "excluir", "id": id_lote})
                if resultado.get("status") == "ok":
                    st.session_state["mensagem"] = f"Lote de '{lote['Produto']}' excluído."
                    st.rerun()
                else:
                    st.error(resultado.get("mensagem", "Não foi possível excluir o lote."))


# ---------------------------------------------------------
# Aba de baixas (vendas e descartes)
# ---------------------------------------------------------
def aba_baixados(movimentos):
    if movimentos.empty:
        st.info("Nenhuma baixa registrada ainda.")
        return

    col1, col2, col3 = st.columns(3)
    tipos = col1.multiselect("Tipo", ["venda", "descarte"], default=["venda", "descarte"], key="filtro_tipo")
    motivos = col2.multiselect("Motivo do descarte", MOTIVOS, default=MOTIVOS, key="filtro_motivo")
    minimo = col3.number_input(
        "Quantidade mínima (por registro)", min_value=0, value=0, step=1, key="filtro_qtd"
    )

    eh_venda = movimentos["Tipo"] == "venda"
    filtro = (
        movimentos["Tipo"].isin(tipos)
        & (eh_venda | movimentos["Motivo"].isin(motivos))
        & (movimentos["Quantidade"] >= minimo)
    )
    filtrado = movimentos[filtro]

    if filtrado.empty:
        st.info("Nenhuma baixa com esses filtros.")
        return

    exibir = filtrado.sort_values("Data", ascending=False).copy()
    exibir["Data"] = exibir["Data"].dt.strftime("%d/%m/%Y")
    st.dataframe(
        exibir[["Data", "Produto", "Tipo", "Quantidade", "Motivo"]],
        use_container_width=True,
        hide_index=True,
    )

    descartes = filtrado[filtrado["Tipo"] == "descarte"]
    if not descartes.empty:
        st.markdown("**Total descartado por produto**")
        total = (
            descartes.groupby("Produto", as_index=False)["Quantidade"]
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
if "erro" in st.session_state:
    st.warning(st.session_state.pop("erro"))

# ---------------------------------------------------------
# Cadastro de lote
# ---------------------------------------------------------
with st.expander("➕ Cadastrar novo lote", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Nome do produto", key="nome")
        st.selectbox(
            "Categoria",
            CATEGORIAS,
            index=None,
            placeholder="Selecione uma categoria",
            key="categoria",
        )
        st.number_input(
            "Quantidade em estoque",
            min_value=1,
            step=1,
            value=None,
            placeholder="Digite a quantidade",
            key="quantidade",
        )
    with col2:
        st.date_input("Data de entrada", value=date.today(), format="DD/MM/YYYY", key="data_entrada")
        st.date_input("Data de validade", value=date.today(), format="DD/MM/YYYY", key="data_validade")

    st.button(
        "Salvar lote",
        on_click=salvar_lote_callback,
        type="primary",
        use_container_width=True,
    )

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

descartes = movimentos[movimentos["Tipo"] == "descarte"]
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
aba_todos, aba_3dias, aba_vencidos, aba_baixas = st.tabs([
    "Todos os produtos",
    "Vencendo em 3 dias",
    "Produtos vencidos",
    "Produtos baixados",
])

with aba_todos:
    mostrar_lotes(com_estoque, "todos")
    if not com_estoque.empty:
        buffer = io.StringIO()
        formatar_datas(com_estoque)[COLUNAS_EXPORTACAO].to_csv(buffer, index=False)
        st.download_button(
            label="⬇️ Exportar produtos (CSV)",
            data=buffer.getvalue(),
            file_name=f"produtos_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True,
        )

with aba_3dias:
    mostrar_lotes(vencendo_3, "3dias")

with aba_vencidos:
    mostrar_lotes(vencidos, "vencidos")

with aba_baixas:
    aba_baixados(movimentos)

st.caption("Protótipo desenvolvido para fins acadêmicos — Projeto Integrador em Ciência de Dados I (UFMS Digital).")

with aba_desc:
    aba_descartes(movimentos)

st.caption("Protótipo desenvolvido para fins acadêmicos — Projeto Integrador em Ciência de Dados I (UFMS Digital).")
