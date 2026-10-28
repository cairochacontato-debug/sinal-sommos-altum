# SINAL | Próxima etapa: Radar visual e regional

## Arquivos para atualizar no GitHub

**Substituir apenas** `scripts/update.py` e `assets/app.js` na branch `main`, mantendo esses caminhos. Não apagar pastas nem sobrescrever `data/latest.json`.

## O que muda

- **RUN**: novas consultas para Salvador, Bahia, treinões, inscrições, corridas e ativações, janela de 14 dias para cases, com prioridade regional.
- **Negócios locais**: consultas para inauguração, franquias, comércio, startups, cafeterias, investimentos e marcas da Bahia, com prioridade regional.
- **Radar Internacional**: 8 buscas no YouTube por campanhas, criadores, branded content e running, usando métricas públicas via chave `YOUTUBE_API_KEY`. Até 20 vídeos; se nenhum for elegível, a seção não inventa links.
- **Fotografias**: tenta usar o `og:image` do site original de até 30 matérias, quando a fonte permite. Mostra imagem conceitual em caso de bloqueio; não cria fotos falsas.
- **Idioma**: mantém todos os títulos e resumos do SINAL traduzidos para português pelo fluxo já existente (`OPENAI_API_KEY`).

## Configurar a API do YouTube

1. Abra https://console.cloud.google.com/apis/library/youtube.googleapis.com e ative **YouTube Data API v3** em um projeto Google Cloud.
2. Em **APIs & Services > Credentials**, crie uma API key e restrinja a chave à **YouTube Data API v3**. Configure limites de cota adequados.
3. Em https://github.com/cairochacontato-debug/sinal-sommos-altum/settings/secrets/actions, crie o secret `YOUTUBE_API_KEY`. Nunca cole a chave em código ou arquivos públicos.
4. Faça commit dos dois arquivos acima.
5. Acesse https://github.com/cairochacontato-debug/sinal-sommos-altum/actions/workflows/publicar-jornal.yml, clique **Run workflow** na branch `main` e confira **Success**.
6. Abra https://sinal.sommosaltum.agency e valide imagens, notícias regionais e referências de vídeos.

### Limitações

- A API do YouTube não garante 10 vídeos bons todos os dias. O SINAL prioriza fontes e não afirma viralidade sem evidências adequadas.
- A API não fornece acesso universal a estatísticas de Instagram/TikTok. O arquivo `config/virais.json` continua permitindo URLs verificadas manualmente.
- O `og:image` de veículos pode bloquear o carregamento no navegador. Nesse caso, o fallback local permanece.
- A rotina de RSS não equivale a um calendário oficial de corridas: confira links organizadores e datas antes de divulgar.
- O sistema pode publicar menos que dez artigos em uma editoria se não houver fontes confiáveis disponíveis.
- O GitHub Actions já tem `OPENAI_API_KEY` configurada; não a substitua.
