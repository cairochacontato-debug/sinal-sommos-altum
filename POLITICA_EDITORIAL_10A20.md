# Política Editorial do SINAL 7.0 (substitui a antiga regra de 10 a 20 por editoria)

O SINAL agora publica **no máximo 40 notícias em toda a edição**, independentemente de quantas editorias existam. Não há cota mínima: se apenas 25 fontes apresentarem conteúdo útil, publicamos 25. Não preencher por número.

## Critério central: aplicação prática
Cada notícia deve gerar uma decisão, um teste, um formato, uma mudança de campanha ou uma oportunidade operacional. Pergunta editorial obrigatória: **qual experimento concreto isso permite, e qual métrica observar?**

### Editorias
Marketing (tráfego, CRO, criativos, conversão); Plataformas (Instagram, Meta, Google Ads, TikTok, YouTube); IA (ferramentas e fluxos de trabalho); Negócios (modelos replicáveis, aquisição, retenção); Creators (formato, distribuição, monetização); Brand + Creators (UGC, campanhas e parcerias); Marcas (posicionamento, experiência, rebranding); Local (casos de negócios na Bahia com aprendizado replicável); RUN (Brasil todo: corridas, comunidades, patrocínios, operações e ativações); Saúde & Migo (telemedicina, healthtech, psicologia, benefícios corporativos, saúde ocupacional e NR-1).

### Excluir
Fofocas e vida pessoal, celebridades sem case operacional, Anitta e entretenimento, notícias policiais/tragédias, política genérica, futebol sem relevância de marketing, ganhos bilionários sem metodologia, corridas metafóricas ou corridas de shows, artigos sem fonte/data, conteúdo duplicado, e afirmações de resultados não comprovados.

### Integridade
Usar fontes com links, datas e contexto. Não converter US$ em R$. Não transformar testes de plataformas em lançamentos gerais. Não inferir causalidade de melhorias de CTR/ROAS sem metodologia e não dar aconselhamento médico. A análise é hipótese para teste, não garantia de resultado.

O Radar Internacional é uma seção de referências em vídeo **separada das 40 notícias**. Vídeos exigem links e métricas verificáveis; excluir tutoriais genéricos, gossip e comentários não relacionados a campanhas.

### Antes de publicar
Usar `python -m py_compile scripts/update.py` e `node --check assets/app.js`. Em seguida confirmar distribuição por editoria, contagem global <= 40, manchetes em PT-BR, vídeos com fonte, e que os cards "Para fazer hoje" abram estratégias.
