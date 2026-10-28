# SINAL 7.0 - CURADORIA ACIONÁVEL

## Atualização única, SEM publicar agora
Apenas estes arquivos precisam ser substituídos/adicionados no GitHub:
- `scripts/update.py` (substituir)
- `assets/app.js` (substituir)
- `assets/styles.css` (substituir)
- `index.html` (substituir)
- `config/editorial.json` (NOVO, registro das diretrizes)
- `POLITICA_EDITORIAL_10A20.md` (substituir; agora documenta a política 7.0)
- `BANNERS_DIARIOS.md` (substituir; agora 10 editorias)
- `PLANO_EDITORIAL.md` (substituir; agora teto global de 40)

Envie as pastas `scripts`, `assets`, `config` e o arquivo `index.html` PRESERVANDO
seus caminhos, pela raiz da branch `main` no GitHub: Add file > Upload files.
Não apague pastas pré-existentes. Não envie o ZIP comprimido como arquivo do repo.
NÃO precisa mudar `data/`, `.github/` nem suas Secrets.

## O que muda
- NO MÁXIMO 40 notícias no jornal inteiro, nunca por editoria.
- Podem ser menos de 40 se não houver fontes acionáveis suficientes.
- Curadoria com exclusão de famosos, fofocas, política genérica, crimes, tragédias e assuntos não operacionais.
- 10 editorias, incluindo Saúde & Migo.
- RUN agora cobre o Brasil e boas referências internacionais de ativação esportiva.
- IA escolhe notícias por aplicação prática e gera por matéria o porquê e o teste com métrica.
- Radar Internacional deixa de promover vídeos genéricos/tutoriais fora do foco.
- Mantida correção: cards de "Para fazer hoje" abrem estratégia detalhada, passos, entregável, métrica e copiar.
- Preservadas fontes, datas, vídeo público verificado e tradução em português.
- A Meta Ads, Instagram e afins podem TESTAR funcionalidades; não afirmar disponibilidade geral.

## Atenção
Esta entrega NÃO atualiza a edição armazenada automaticamente. Após você fazer upload,
o site publicado seguirá na edição anterior até a próxima execução do workflow.
Você solicitou NÃO rodar 'Publicar jornal diário' agora, por isso NÃO foi executado.
O funcionamento de coleta online/OpenAI/YouTube só pode ser validado em execução real no GitHub,
porque este ambiente de teste não tem internet nem segredos do projeto.
A triagem e a geração de estratégias consomem tokens na API OpenAI; limitar a 40 reduz
itens traduzidos, mas os custos totais dependem das chamadas de seleção e curadoria.
