# Portal Logística

O portal reúne os módulos da logística. Atualmente inclui o módulo
**Identificação de Pallets**, com os fluxos de Fios e Painel/Kits.

Recriação em Flask (Python + HTML/CSS/JS) da planilha `PCP - PACKINGLIST` (abas
`FIOS_` e `PAINEL_KITS`, macros `MóduloFios` / `MóduloKIT_Painel`). Sistema
**novo e independente** do Portal PCP / sistema Funil já existente — não
compartilha banco nem código com ele.

## O que foi recriado

- **Home** com os módulos Fios, Painel/Kits, Histórico e Configurações, igual ao
  conceito da aba `HOME` da planilha.
- **Módulo Fios / Painel**: você digita apenas **OP** e **Qtde** por linha — OC,
  Pedido, Código, Descrição, Tipo (NU/PMC/PKT) e NCM vêm automaticamente do
  cache local, que é alimentado pelo ERP. Mesma ideia do `XLOOKUP` da planilha
  contra a aba oculta `Funil`.
- **Repetição rápida de OP**: o botão **Repetir última OP** cria a próxima linha
  com a mesma OP e os dados já consultados. Também é possível pressionar
  **Enter** no campo de quantidade para repetir a OP e continuar digitando os
  pesos dos carretéis sem usar o mouse.
- **Validação de cliente único por palete**: se as OPs digitadas pertencerem a
  clientes diferentes, o sistema avisa antes de deixar gravar — equivalente ao
  que a fórmula `AVERAGE`/`XLOOKUP` fazia em `B4`/`B9` da planilha.
- **Cálculo automático de peso**: peso líquido = soma das quantidades; peso
  bruto = líquido + tara por carretel (6,2 kg para PMC/PKT, 19,3 kg para NU) +
  peso da embalagem do palete (tabela configurável, igual à aba `PALETES`).
- **Numeração sequencial automática** do palete (equivalente a `MAX(Base!L:L)+1`).
- **Gravar** e **Gravar e Imprimir**: os dois salvam no histórico e geram o PDF
  da etiqueta/packing list em `C:\Users\miguel.santos\Documents\pdf_packing_list`;
  "Gravar e Imprimir" também abre o PDF para impressão. O destino pode ser
  alterado pela variável de ambiente `PACKING_LIST_PDF_DIR`.
- **Limpar**: com a mesma escolha da planilha (limpar tudo, ou manter a OP e
  limpar só a quantidade, para gerar outro palete da mesma OP).
- **Histórico** = equivalente à aba oculta `Base`.
- **Dados do ERP**: mostra até 1.000 linhas do cache local, com busca e filtro
  por módulo. OP, OC, pedido, produto, descrição, cliente e tipo podem ser
  editados pela tela. Uma nova atualização do ERP substitui os ajustes locais.
- **Configurações**: tabela de medidas de palete (tara) e tabela de abreviação
  de clientes usada no nome do PDF (equivalente às colunas `IP:IQ` da aba
  `Cliente`) — ambas editáveis pela tela, sem precisar mexer em planilha/VBA.
- **Teste de saída do PDF**: nas Configurações, permite conferir separadamente
  os modelos de Fios e de Painel/Kits, sem incluir o teste no histórico.

## ⚠️ O que você precisa revisar antes de usar de verdade

1. **`src/queries.py`** — as consultas de Ordem de Produção (`ORDENS_QUERY_FIOS`
   e `ORDENS_QUERY_PAINEL`) são um ponto de partida baseado nas tabelas padrão
   do Protheus (`SC2010`, `SC6010`, `SB1010`). Eu não consegui decodificar o
   código M da Power Query "Funil" original de dentro do `.xlsm` (fica
   comprimido em binário), então não tenho certeza de que os nomes de campo
   batem exatamente com a customização de vocês. Rode a query direto no SSMS,
   compare com o resultado que a planilha mostra na aba `Funil`, e ajuste os
   nomes de campo se precisar — o resto do sistema não muda.
2. A regra de peso do módulo **Painel/Kits** está deixada simples (peso bruto =
   peso líquido + tara do palete, sem tara por item) porque eu não abri a aba
   `PAINEL_KITS`/`MEDIDAS_CORRUGADO` a fundo. Se lá existir uma tara por
   dimensão do painel, me diga a regra que eu ajusto em `server.py`
   (função `api_pallets_gravar`, variável `tara`).
3. **Conexão com o TOTVS**: o sistema tenta primeiro o driver ODBC configurado.
   Se a máquina tiver apenas o driver legado e a conexão falhar, usa
   automaticamente o cliente SQL nativo do Windows/.NET. As duas opções usam
   os mesmos dados de acesso do `config.json`.

## Rodando

Copie `config.example.json` para `config.json` e preencha os dados de conexão com o TOTVS. O arquivo de configuração real, o banco local e os arquivos gerados não são versionados.

```bash
pip install -r requirements.txt --break-system-packages
python server.py
```

Abra `http://localhost:3010` (porta configurável em `config.json`, campo
`porta_do_sistema`). No Windows, dê duplo clique em `iniciar.bat`.

## Estrutura

```
config.json          # conexao com o TOTVS + porta do sistema
requirements.txt
paths.py
db.py                 # schema SQLite local (cache_ordens, cache_clientes,
                       # clientes_abrev, paletes, pallets/histórico)
src/
  mssql.py             # conexao SQL auth com o TOTVS (pyodbc)
  queries.py           # queries do ERP (AJUSTAR - ver aviso acima)
  refresh.py           # puxa ERP -> cache local (botao "Atualizar dados do ERP")
  etiqueta.py           # gera o PDF do packing list (reportlab)
public/
  index.html / style.css / app.js   # front-end (SPA simples, sem framework)
```

## Diferenças em relação à planilha original

- Módulos Fios e Painel/Kits compartilham a mesma numeração sequencial e o
  mesmo histórico (`pallets`), assim como na planilha (as duas macros gravavam
  na mesma aba `Base`).
- Não recriei a senha de proteção de abas (da planilha original) porque, num sistema
  web, quem acessa o servidor já é controlado por rede/porta — não faz sentido
  repetir uma senha fixa em texto puro no código, que era a fragilidade que eu
  já tinha apontado na planilha.
- Não incluí tela de login: este sistema ficou focado só na identificação de
  pallets. Se quiser, dá para reaproveitar o mesmo padrão de login (usuarios.json
  + sessão) que já existe no seu sistema Funil.

