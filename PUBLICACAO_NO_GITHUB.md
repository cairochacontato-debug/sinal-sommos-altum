# Publicar o SINAL em sinal.sommosaltum.agency

Repositório: https://github.com/cairochacontato-debug/sinal-sommos-altum

1. Extraia o ZIP **antes** de enviar ao GitHub. Envie **o conteúdo da pasta**, e não o ZIP, para a raiz do repositório: index.html, assets/, data/, scripts/, config/, .github/, .nojekyll, CNAME, requirements.txt, etc.
2. No GitHub: repositório > Add file > Upload files. Se ainda estiver vazio, use "uploading an existing file" na tela inicial. Arraste os arquivos e pastas extraídos, incluindo a pasta oculta `.github`, e confirme "Commit changes". No Mac, `Command + Shift + .` mostra arquivos ocultos no Finder.
3. Settings > Pages > Build and deployment > Source: **GitHub Actions**.
4. Settings > Pages > Custom domain deve mostrar `sinal.sommosaltum.agency`. A raiz possui `CNAME` com esse endereço. Para DNS, no seu gerenciador de domínio, o registro `CNAME` do host `sinal` deve apontar para `cairochacontato-debug.github.io` (sem `https://`). Se houver registro conflitante para o mesmo host, ajuste no provedor.
5. Actions > Publicar jornal diário > Run workflow > Run workflow. O workflow instala dependências, busca notícias via RSS, salva a edição (quando há fontes válidas) e publica pelo GitHub Pages. Confira o resultado em Settings > Pages, Actions ou Deployments. O DNS/HTTPS pode levar algum tempo para propagar e ser ativado.
6. Para resumos mais elaborados, adicione **OPENAI_API_KEY** em Settings > Secrets and variables > Actions > New repository secret. Opcional: **YOUTUBE_API_KEY** para vídeos da API do YouTube. Nunca coloque chaves em HTML ou no repositório público.
7. O workflow está agendado para **7h20 de Salvador**, com objetivo de deixar a edição pronta pela manhã. GitHub Actions não garante execução pontual.

A versão inicial contém apenas a edição demonstrativa existente; a meta de 10–20 matérias por editoria é editorial, não preenchimento automático garantido. A coleta de Reels/TikToks e o observatório de marcas/criadores ainda dependem de integrações e fontes adicionais.
