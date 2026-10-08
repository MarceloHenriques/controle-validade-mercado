// Nomes das abas da planilha
var ABA_LOTES = "Sheet1";
var ABA_MOVIMENTOS = "Movimentos";

var CABECALHO_LOTES = ["Produto", "Categoria", "Data de entrada", "Data de validade", "Quantidade", "ID"];
var CABECALHO_MOVIMENTOS = ["Data", "ID do lote", "Produto", "Tipo", "Quantidade", "Motivo"];

// Responde quando o app pede dados (GET)
function doGet(e) {
  var acao = (e && e.parameter && e.parameter.acao) ? e.parameter.acao : "";

  if (acao === "movimentos") {
    return responder(lerAba(ABA_MOVIMENTOS, CABECALHO_MOVIMENTOS));
  }
  return responder(lerAba(ABA_LOTES, CABECALHO_LOTES));
}

// Recebe cadastros de lote e baixas (POST)
function doPost(e) {
  var corpo = JSON.parse(e.postData.contents);

  if (corpo.acao === "baixa") {
    return responder(darBaixa(corpo));
  }
  return responder(cadastrarLote(corpo));
}

function responder(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

// Pega a aba pelo nome. Se ela não existir, cria. Se estiver vazia, escreve o cabeçalho.
function pegarAba(nome, cabecalho) {
  var planilha = SpreadsheetApp.getActiveSpreadsheet();
  var aba = planilha.getSheetByName(nome);
  if (!aba) {
    aba = planilha.insertSheet(nome);
  }
  if (aba.getLastRow() === 0) {
    aba.getRange(1, 1, 1, cabecalho.length).setValues([cabecalho]);
  }
  return aba;
}

// Lê a aba e transforma cada linha em um objeto (o nome da coluna vira a chave)
function lerAba(nome, cabecalho) {
  var aba = pegarAba(nome, cabecalho);
  var dados = aba.getDataRange().getValues();

  if (dados.length < 2) {
    return [];
  }

  var titulos = dados[0];
  var resultado = [];

  for (var i = 1; i < dados.length; i++) {
    var linha = dados[i];
    if (linha.join("") === "") {
      continue; // pula linhas em branco
    }

    var obj = {};
    for (var j = 0; j < titulos.length; j++) {
      var valor = linha[j];
      if (valor instanceof Date) {
        valor = Utilities.formatDate(valor, Session.getScriptTimeZone(), "yyyy-MM-dd");
      }
      obj[titulos[j]] = valor;
    }
    resultado.push(obj);
  }
  return resultado;
}

// Gera um código curto e único para cada lote
function gerarId() {
  return Utilities.getUuid().substring(0, 8);
}

// Cadastro de um novo lote
function cadastrarLote(corpo) {
  var aba = pegarAba(ABA_LOTES, CABECALHO_LOTES);
  var id = gerarId();

  aba.appendRow([
    corpo.produto,
    corpo.categoria,
    corpo.data_entrada,
    corpo.data_validade,
    corpo.quantidade,
    id
  ]);

  return {status: "ok", id: id};
}

// Dá baixa (venda ou descarte) em um lote
function darBaixa(corpo) {
  var quantidadeBaixa = Number(corpo.quantidade);

  if (!(quantidadeBaixa > 0)) {
    return {status: "erro", mensagem: "A quantidade precisa ser maior que zero."};
  }
  if (!corpo.id) {
    return {status: "erro", mensagem: "Lote sem ID. Rode a função prepararPlanilha()."};
  }
  if (corpo.tipo === "descarte" && !corpo.motivo) {
    return {status: "erro", mensagem: "Informe o motivo do descarte."};
  }

  var aba = pegarAba(ABA_LOTES, CABECALHO_LOTES);
  var dados = aba.getDataRange().getValues();
  var cabecalho = dados[0];

  var colId = cabecalho.indexOf("ID");
  var colProduto = cabecalho.indexOf("Produto");
  var colQtd = cabecalho.indexOf("Quantidade");

  if (colId === -1) {
    return {status: "erro", mensagem: "Coluna ID não encontrada. Rode a função prepararPlanilha()."};
  }

  for (var i = 1; i < dados.length; i++) {
    if (String(dados[i][colId]) === String(corpo.id)) {
      var atual = Number(dados[i][colQtd]);

      if (quantidadeBaixa > atual) {
        return {status: "erro", mensagem: "A quantidade informada é maior que o estoque do lote (" + atual + ")."};
      }

      var novaQuantidade = atual - quantidadeBaixa;
      aba.getRange(i + 1, colQtd + 1).setValue(novaQuantidade);

      registrarMovimento(corpo.id, dados[i][colProduto], corpo.tipo, quantidadeBaixa, corpo.motivo || "");

      return {status: "ok", restante: novaQuantidade};
    }
  }

  return {status: "erro", mensagem: "Lote não encontrado."};
}

// Guarda uma linha na aba Movimentos para cada venda ou descarte
function registrarMovimento(id, produto, tipo, quantidade, motivo) {
  var aba = pegarAba(ABA_MOVIMENTOS, CABECALHO_MOVIMENTOS);
  aba.appendRow([new Date(), id, produto, tipo, quantidade, motivo]);
}

// Rode esta função UMA vez, pelo editor do Apps Script (botão Executar).
// Ela cria a coluna ID na aba Sheet1 e gera um ID para cada lote que ainda não tem.
function prepararPlanilha() {
  var aba = pegarAba(ABA_LOTES, CABECALHO_LOTES);
  var dados = aba.getDataRange().getValues();

  var colId = dados[0].indexOf("ID");
  if (colId === -1) {
    colId = dados[0].length;
    aba.getRange(1, colId + 1).setValue("ID");
  }

  for (var i = 1; i < dados.length; i++) {
    if (dados[i][0] === "") {
      continue; // linha sem produto
    }
    if (!dados[i][colId]) {
      aba.getRange(i + 1, colId + 1).setValue(gerarId());
    }
  }
}

  return ContentService.createTextOutput(JSON.stringify({status: "ok"}))
    .setMimeType(ContentService.MimeType.JSON);
}
