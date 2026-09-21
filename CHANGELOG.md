# Changelog

Todas as alterações relevantes deste projeto serão documentadas neste arquivo.
O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/)
e o projeto adota [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

## [2.0.0] - 2026-09-21

### Adicionado

- Campo `chave_acesso` nos blocos `NFO` e `NFD`, com normalização para 44
  dígitos e validação do dígito verificador da NF-e.
- OCR documental da Mistral para PDFs digitalizados sem camada textual, usado
  como fonte de conferência para chaves, CNPJs, peso e demais campos críticos.
- Segunda leitura visual focada quando uma chave continua ausente após o OCR.
- Controle centralizado de versão em `App/_version.py`, exportado pelo pacote
  `App` e reutilizado pelo OpenAPI e pelo healthcheck.
- Testes de regressão para as notas 10, 31679, 104942 e 354644, incluindo
  validação de chaves, inversão NFO/NFD, campos ausentes e anexos indevidos.

### Alterado

- `NFD` passa a representar a nota de devolução, retorno ou estorno exibida na
  DANFE atual; `NFO` passa a representar exclusivamente a nota fiscal original
  referenciada.
- Cada página do PDF é renderizada separadamente e em maior resolução para
  preservar a legibilidade durante a análise visual.
- O prompt de extração deixou de conter dados reais de exemplo e agora exige a
  omissão de qualquer informação ilegível ou não comprovada.
- Nome, extensão e tamanho do arquivo são derivados do upload, sem depender da
  resposta do modelo de IA.
- A API e os JSONs persistidos deixam de emitir propriedades com valor nulo.
- Todos os provedores passaram a aplicar a mesma reconciliação e validação
  defensiva após a resposta da IA.
- O cliente de testes passou a interpretar a estrutura `notaFiscalList`, usar a
  porta configurada pela aplicação e aceitar o provedor `mistral`.
- O template de dados e a documentação de uso foram atualizados para o novo
  contrato.

### Corrigido

- Alucinações causadas pelos exemplos preenchidos existentes no prompt antigo.
- Contagem incorreta de DACTEs, etiquetas, comprovantes e fotos como novas
  notas fiscais.
- Inversão entre emitente e destinatário e repetição do mesmo CNPJ nas duas
  entidades.
- Inversão entre a nota de devolução atual e a nota original referenciada.
- Uso indevido de peso, cubagem ou valor do DACTE como dados da DANFE.
- Uso de motivo da devolução como número de pedido.
- Datas parciais de mês/ano completadas artificialmente com um dia inexistente.
- Séries e números inconsistentes; quando há chave válida, esses campos agora
  são reconciliados com as posições oficiais da chave.
- Inicialização com valores de ambiente como `DEBUG=release`.

### Validação

- Extração real das quatro amostras executada contra Mistral/Pixtral e Mistral
  OCR.
- Dez testes automatizados de regressão aprovados.
- Compilação dos módulos, geração do OpenAPI e leitura do template JSON
  validadas.

### Compatibilidade

- Esta é uma versão principal porque corrige o significado público de `NFO` e
  `NFD`, adiciona `chave_acesso` a cada nota e passa a omitir campos ausentes.

> O histórico anterior à versão 2.0.0 não possuía changelog estruturado.
