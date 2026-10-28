## NOVA REGRA: 10 a 20 por editoria (v5)
- Cada uma das **9 editorias** pode publicar até **20 fontes/cases verificáveis por edição**. O total máximo teórico é **180 matérias**. O mínimo de **10 é uma meta editorial de cobertura**, não uma autorização para inventar, repetir ou criar URL.
- O **Radar Internacional** busca até 20 referências de vídeo, também com meta 10, mas requer links verificáveis e acesso às fontes. Não é preenchido automaticamente com Reels/TikToks sem APIs e curadoria.
- A IA pode enriquecer os destaques sem eliminar o restante da seleção por editoria. Ranking inicial considera recência, termos do tema e evidências no feed, sempre passível de revisão editorial.
- Um banner por área (agora **9 banners**), mas o banner **não aumenta a contagem**. Clique na editoria no menu e carregue as notícias de 6 em 6.
- Creators e RUN podem incluir estudos de até 7 dias; Brands, Local e Brand + Creators até 14 dias. As notícias gerais priorizam 48 horas. Veja as datas individuais.
- Dados de teste não fazem parte das edições reais. A edição inaugural permanece curta até rodar uma coleta efetiva na hospedagem.
- Com máximo teórico elevado, a revisão de fontes/duplicidade torna-se ainda mais importante; não equipare frequência de publicação a qualidade da curadoria.

# SINAL. — Edição visual e editorial 5.0

## Atualização
- Prioridade para fotografias conceituais e leitura rápida, estética macOS/Apple.
- 9 imagens editoriais próprias em `assets/editorial/` (geradas por IA), distribuídas entre capa, atalhos, notícias, observatório e laboratório de ideias.
- Cada imagem é ilustrativa: NÃO representa conteúdo efetivamente postado, marca real, entrevista ou notícia.
- Para novas edições, o coletor lê miniaturas disponibilizadas em RSS e na API do YouTube, adicionando `image` aos itens. Se a imagem não existir ou falhar, usa fotografia conceitual local.
- Links de notícias e vídeos não são inventados; seção internacional mostra exemplos de formatos claramente identificados como demonstração quando não há vídeos verificados.
- Arquivo auto-suficiente, imagens sem dependência de CDN.

# SINAL. | Uma publicação SOMMOS ALTUM

Jornal digital e observatório **responsivo**, com edições datadas, leitura de matérias com links originais, filtros, busca, salvos no navegador e arquivo das edições.

## O que já funciona

- `index.html` já utiliza a marca SINAL e abre uma edição inaugural mesmo sem internet ou servidor (textos e links na pasta `data/`);
- Ao ser hospedado, carrega `data/latest.json` automaticamente;
- As seções do observatório (Creators, Brand + Creators, Rising Brands, Local e RUN) são exibidas sem casos inventados. Para ativar casos, preencha `data/watchlist.json` com fontes verificadas. A curadoria e o monitoramento destas cinco categorias AINDA NÃO SÃO AUTOMÁTICOS;
- Marcadores de artigos salvos ficam no navegador; há busca e filtros por categoria;
- Rotina Python consulta feeds RSS de veículos de tecnologia, marketing e mídia;
- Notícias com data e URL são priorizadas nas últimas 48 horas;
- Se houver `OPENAI_API_KEY`, a IA escreve resumos e sugere ações com base nos títulos e trechos verificados dos feeds, sem modificar links;
- O workflow do GitHub Actions busca fontes e publica o jornal todos os dias às **7h20 de Salvador** (o site tende a estar pronto para leitura por volta das 8h, mas execução/publicação podem atrasar);
- Se a coleta falhar ou tiver menos de 3 notícias relevantes, a última edição é mantida;
- O jornal não fabrica Reels, links ou números de visualizações. A seção social recebe links manuais de `config/virais.json` e, opcionalmente, vídeos recentes com métricas públicas verificadas via YouTube Data API (`YOUTUBE_API_KEY`).

## Como publicar (GitHub Pages)

1. Crie um repositório **público** no GitHub para o jornal (a hospedagem padrão de Pages ficará pública).
2. Extraia este ZIP e envie **todos os arquivos, incluindo `.github/` e `.nojekyll`**, para a raiz do repositório.
3. Em **Settings → Pages → Build and deployment**, selecione **Source: GitHub Actions**.
4. Em **Settings → Secrets and variables → Actions → New repository secret**, cadastre `OPENAI_API_KEY` se quiser resumos e insights redigidos por IA. Nunca coloque a chave no HTML ou em arquivos versionados. Sem chave, a coleta RSS continua com análise básica. Se quiser captar vídeos internacionais com dados reais de views, acrescente também o secret `YOUTUBE_API_KEY` usando uma chave do YouTube Data API v3 com quota. Essa integração é opcional e não garante posts virais.
5. Abra **Actions → Publicar jornal diário → Run workflow** para executar uma publicação manual. O link será exibido na aba de Pages / Deployments.
6. Para usar seu domínio, configure **Settings → Pages → Custom domain** e os registros DNS indicados pelo GitHub. Exemplos: `sinal.sommosaltum.agency` (mediante configuração do DNS e do custom domain).
7. Confira a execução agendada e os links das fontes. Workflows agendados podem atrasar ou deixar de executar em certas condições da plataforma. Verifique a aba Actions em caso de atraso.

## Como alimentar o radar social

Os feeds de notícias não comprovam se um Reel ou Short viralizou. Há um arquivo `config/virais.json` com array JSON de vídeos a verificar, preenchido manualmente. Exemplo:

```json
[
  {
    "title": "Descrição do vídeo original",
    "url": "https://www.youtube.com/watch?v=ID_REAL",
    "platform": "YouTube",
    "language": "EN",
    "insight": "Por que observar esta abertura e como adaptá-la",
    "published_at": "2026-10-28",
    "verified": true
  }
]
```

Use **somente URLs verdadeiras** que foram abertas e verificadas. O campo `verified` não é verificado por API, portanto depende da curadoria. Evite chamar um conteúdo de viral sem verificar métricas públicas e a data. Para monitorar virais automaticamente com estatísticas, desenvolva uma etapa adicional via APIs oficiais das plataformas onde for permitido. O coletor atual oferece a integração opcional com a YouTube Data API, mas não fornece coleta automática de Reels/TikToks nem valida crescimento real sem dados históricos.

## Testar no próprio computador

Abra `index.html` com duplo clique. Ele mostrará a edição inicial, inclusive sem servidor. Para testar o carregamento automático de JSON e os arquivos de edições anteriores:

```bash
python -m http.server 8000
```

Abra `http://localhost:8000`. Para testar a coleta RSS:

```bash
pip install -r requirements.txt
python scripts/update.py
```

O coletor depende da disponibilidade dos feeds, de rede e de uma quantidade mínima de notícias relevantes. Se não houver notícias suficientes, ele não altera o jornal.

## Escopo e transparência

Este é um MVP utilizável para um **jornal de notícias com curadoria**. O resumo é feito a partir de títulos e trechos presentes nos feeds, não de acesso ao conteúdo integral de cada artigo. O projeto não implementa login, paywall ou acesso privado. O arquivo do projeto pode ser publicado num repositório público; nunca inclua informações pessoais, senhas ou chaves. A tarefa de briefing diário no ChatGPT é independente do agendamento do site; uma não publica automaticamente na outra.

## Observatório de marcas, criadores e corrida

O arquivo `data/watchlist.json` inicia com listas vazias: `creators`, `collaborations`, `brands`, `local`, `run`. Cada lista aceita objetos com os campos `title`, `region`, `date` (ISO, YYYY-MM-DD), `summary`, `source_url` (HTTPS) e `verification` (um de `confirmado`, `indício`, `hipótese`). Só há exibição quando existe título e fonte HTTPS. Não publique indicadores de vendas, receita, crescimento ou taxa de engajamento sem fonte e recorte temporal.

A estratégia de coleta está em `PLANO_EDITORIAL.md`. Para automação de métricas de Instagram, TikTok, Meta Ads e negócios locais, é necessário avaliar permissões e limites das respectivas plataformas e manter um processo de revisão editorial. A existência das editorias no site NÃO significa que o monitoramento esteja conectado.

**Próximo passo operacional:** criar um repositório público no GitHub, autorizar o aplicativo GitHub a acessar o repositório, publicar este diretório no Pages e configurar o domínio `sinal.sommosaltum.agency`. O DNS só pode ser configurado com acesso ao provedor de domínio.


## Novidade: banners editoriais de capa (v4)

O jornal abre com um carrossel de 9 áreas e uma manchete rastreável por área, sempre que há notícia recente: Marketing, Plataformas, IA, Negócios, Creators, Marcas, Local e RUN. Dados em `data/latest.json > highlights`; imagens ilustrativas são identificadas como tal. Cada nova edição recompõe os banners pela rotina automatizada; sem fonte recente, o estado de curadoria permanece claro. Veja `BANNERS_DIARIOS.md`.
