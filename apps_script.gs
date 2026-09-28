function doGet(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Sheet1");
  var dados = sheet.getDataRange().getValues();

  if (dados.length === 0) {
    return ContentService.createTextOutput(JSON.stringify([]))
      .setMimeType(ContentService.MimeType.JSON);
  }

  var cabecalho = dados[0];
  var linhas = dados.slice(1);
  var resultado = linhas.map(function(linha) {
    var obj = {};
    cabecalho.forEach(function(coluna, i) {
      var valor = linha[i];
      if (valor instanceof Date) {
        valor = Utilities.formatDate(valor, Session.getScriptTimeZone(), "yyyy-MM-dd");
      }
      obj[coluna] = valor;
    });
    return obj;
  });

  return ContentService.createTextOutput(JSON.stringify(resultado))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Sheet1");
  var body = JSON.parse(e.postData.contents);

  // garante o cabeçalho na primeira linha
  var primeiraLinha = sheet.getRange(1, 1, 1, 5).getValues()[0];
  var cabecalhoEsperado = ["Produto", "Categoria", "Data de entrada", "Data de validade", "Quantidade"];
  if (primeiraLinha.join("") === "") {
    sheet.getRange(1, 1, 1, 5).setValues([cabecalhoEsperado]);
  }

  sheet.appendRow([
    body.produto,
    body.categoria,
    body.data_entrada,
    body.data_validade,
    body.quantidade
  ]);

  return ContentService.createTextOutput(JSON.stringify({status: "ok"}))
    .setMimeType(ContentService.MimeType.JSON);
}
