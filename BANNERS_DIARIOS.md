# SINAL / Banners diários por editoria

## O que foi implementado

- Um carrossel panorâmico no início do jornal, substituindo a antiga capa estática, com **8 banners**: Marketing, Plataformas, IA, Negócios, Creators, Rising Brands, Negócios Locais e RUN.
- Uma manchete (quando há fonte recente) e uma imagem grande por banner; data, veículo e botão que abre a análise/fonte.
- Botões anterior/próximo, seleção direta das editorias, toque/deslize no celular, setas do teclado e rotação a cada 8,5 segundos, pausada quando o visitante interage, coloca foco no banner ou prefere redução de movimentos.
- Destaques lidos de `data/latest.json` ou da edição arquivada: cada registro `highlights` contém `area`, `article_id` e `status`. O `article_id` deve corresponder a uma matéria na mesma edição.
- Sempre que a rotina de coleta pública uma nova edição, os banners são recompostos da seleção editorial e atualizados no site. Recarregar o site consulta o arquivo diário.

## Garantias editoriais

- **Não há notícias inventadas.** Se não houver notícia recente (até 48h) para uma área, o banner diz "Ainda sem notícia recente verificada nesta área". Em outras palavras, os slots são diários, mas não há promessa de uma notícia nova em todas as áreas todos os dias.
- Imagens conceituais estão rotuladas como *imagem ilustrativa*. Fotografias da fonte só aparecem como “imagem da fonte” quando o feed fornece um URL HTTPS para a imagem.
- Google Notícias é usado como agregador RSS de Creators, Marcas, Local e RUN; seu link pode redirecionar para o veículo. Nem desempenho comercial de uma marca nem viralidade de um vídeo são presumidos por manchete.
- Quando a coleta falha ou tem menos de três notícias verificáveis, preserva a última edição **com a data original** (sem fingir atualização).

## Automação

A rotina `.github/workflows/publicar-jornal.yml` está programada para 11h UTC (8h em Salvador) e pode ser iniciada manualmente no GitHub Actions. O GitHub Actions pode ter atrasos de agendamento. Para publicar, crie o repositório no GitHub, habilite o Pages, adicione `OPENAI_API_KEY` opcional para análises e `YOUTUBE_API_KEY` opcional para vídeos monitorados.

Os arquivos já estão prontos, mas a publicação no domínio `sinal.sommosaltum.agency` depende de repositório autorizado, Pages e DNS. Este pacote é uma implementação local, não um site já publicado nem um monitoramento que esteja rodando neste momento.


## v5: quantidade e navegação
Nove banners, um por editoria, incluindo Brand + Creators. Clique em uma editoria no menu para ver sua listagem progressiva com até 20 itens, meta editorial mínima de 10, sem fabricar para preencher lacunas. O banner não ocupa vaga adicional: é o primeiro destaque daquela editoria.
