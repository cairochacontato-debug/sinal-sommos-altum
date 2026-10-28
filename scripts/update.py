#!/usr/bin/env python3
"""Coletor de links RSS com curadoria editorial opcional via API.

Nunca fabrica métricas sociais; URLs de fonte são preservadas dos feeds.
Em caso de falha, não substitui edição anterior por conteúdo inventado.
"""
import calendar
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, urlencode, urljoin
from zoneinfo import ZoneInfo
from html.parser import HTMLParser
import ipaddress

import feedparser
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
TZ = ZoneInfo('America/Bahia')
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.astimezone(TZ).date().isoformat()
LOOKBACK = 48
MAX_AGE = dt.timedelta(hours=LOOKBACK)
MIN_PER_SECTION = 10  # meta de curadoria, nunca preencher artificialmente
MAX_PER_SECTION = 20  # teto absoluto por editoria e por edição
SECTION_LOOKBACK = {'Marcas':14, 'Local':14, 'RUN':14, 'Creators':7, 'Brand+Creators':14}  # estudos e casos têm ciclos mais longos
AGENT = 'SinalNewsReader/1.1 (personal curated news reader; contact repo owner)'

FEEDS = [
    ('Search Engine Journal', 'https://www.searchenginejournal.com/feed/'),
    ('Search Engine Land', 'https://searchengineland.com/feed'),
    ('Social Media Today', 'https://www.socialmediatoday.com/feeds/news/'),
    ('TechCrunch', 'https://techcrunch.com/feed/'),
    ('The Verge', 'https://www.theverge.com/rss/index.xml'),
    ('Marketing Dive', 'https://www.marketingdive.com/feeds/news/'),
]

KEYWORDS = {
    'Plataformas': ['instagram','threads','reels','tiktok','youtube','meta ','facebook','linkedin','shorts','creator'],
    'IA': ['artificial intelligence',' ai ','openai','chatgpt','generative','agentic','claude','gemini','model','automation','machine learning'],
    'Marketing': ['ad campaign','advertising','marketing','google ads','brand','campaign','social media','creative','seo','search','cmo','influencer','creator economy'],
    'Negócios': ['startup','business','ecommerce','retail','commerce','subscription','shop','revenue','entrepreneur','consumer','product launch'],
}
BADWORDS = ['fatal','died','killed','murder','shooting','bombing','suicide','tragic','earthquake','war crime','violence','fatalities','hostage','bloodshed','rape','massacre','hurricane deaths','obituary']
TRUST_HOSTS = {urlparse(url).netloc for _,url in FEEDS}

# Fontes adicionais consultadas por assunto. Cada item precisa ter data recente,
# link de origem e palavras-chave específicas da editoria. Não garante manchetes
# em todas as áreas e não inventa conteúdo para preencher slots vazios.
# Múltiplas buscas menores por categoria para ampliar a cobertura sem usar assuntos alheios.
# Cada consulta é restrita a termos editoriais, com idade editorial diferente para cases.
THEME_QUERIES = {
    'Marketing': [
        ('marketing campaigns creative advertising brand strategy', 'en-US','US','US:en'),
        ('marketing publicidade campanha estratégia conteúdo marcas', 'pt-BR','BR','BR:pt')],
    'Plataformas': [
        ('instagram tiktok youtube reels shorts meta ads update', 'en-US','US','US:en'),
        ('instagram tiktok youtube atualizações algoritmo anúncios', 'pt-BR','BR','BR:pt')],
    'IA': [
        ('generative AI agents tools creative business launch', 'en-US','US','US:en'),
        ('inteligência artificial ferramentas automação negócios', 'pt-BR','BR','BR:pt')],
    'Negócios': [
        ('startup entrepreneurship commerce subscriptions retail growth', 'en-US','US','US:en'),
        ('negócios startups varejo comércio expansão empreendedores', 'pt-BR','BR','BR:pt')],
    'Creators': [
        ('creator economy influencers content creators social media', 'en-US','US','US:en'),
        ('criadores conteúdo influenciadores monetização youtube tiktok', 'pt-BR','BR','BR:pt')],
    'Brand+Creators': [
        ('brand influencer partnership UGC creator campaign', 'en-US','US','US:en'),
        ('marca criador influenciador campanha embaixador UGC parceria', 'pt-BR','BR','BR:pt')],
    'Marcas': [
        ('emerging brands rebrand retail launch expansion', 'en-US','US','US:en'),
        ('marcas novas branding reposicionamento expansão lançamento', 'pt-BR','BR','BR:pt')],
    'Local': [
        ('(inaugura OR inauguração OR expande) (Salvador OR Bahia) loja negócio', 'pt-BR','BR','BR:pt'),
        ('empreendedorismo (Salvador OR Bahia) marcas empresas', 'pt-BR','BR','BR:pt'),
        ('(restaurante OR cafeteria OR varejo) (Salvador OR Bahia) inauguração', 'pt-BR','BR','BR:pt'),
        ('(franquia OR startup OR investimento) (Salvador OR Bahia)', 'pt-BR','BR','BR:pt'),
        ('site:atarde.com.br (economia OR inauguração OR empresa) Salvador', 'pt-BR','BR','BR:pt'),
        ('site:correio24horas.com.br (negócios OR empreendedorismo OR comércio) Bahia', 'pt-BR','BR','BR:pt')],
    'RUN': [
        ('(corrida OR maratona OR treinão) (Salvador OR Bahia)', 'pt-BR','BR','BR:pt'),
        ('(inscrições OR calendário) corrida Salvador Bahia', 'pt-BR','BR','BR:pt'),
        ('(corrida OR treinão) (Piatã OR Patamares OR Barra OR Ondina) Salvador', 'pt-BR','BR','BR:pt'),
        ('(run club OR grupo de corrida) (Salvador OR Bahia)', 'pt-BR','BR','BR:pt'),
        ('(corrida de rua OR running) marcas ativações patrocínio', 'pt-BR','BR','BR:pt'),
        ('running club brand activation sports marketing race', 'en-US','US','US:en'),
        ('site:ge.globo.com/ba corrida Salvador inscrição', 'pt-BR','BR','BR:pt')],
}
AREA_TERMS = {
    'Marketing': ['marketing','advertis','publicidade','campanha','creative','criativo','branding','brand'],
    'Plataformas': ['instagram','meta','tiktok','youtube','reels','shorts','algoritmo','plataforma','social media'],
    'IA': ['ai','inteligência artificial','artificial intelligence','chatgpt','agent','modelo','automação','automati','gemini'],
    'Negócios': ['negóci','business','startup','comérci','commerce','ecommerce','retail','varejo','empreend','subscription'],
    'Creators': ['creator','influencer','criador','influenciador','ugc','tiktoker','youtuber'],
    'Brand+Creators': ['creator','influencer','criador','influenciador','ugc','embaixador','parceria'],
    'Marcas': ['brand','marca','branding','campanha','identidade','rebrand','expans'],
    'Local': ['salvador','bahia','baiano','baiana','feira de santana','recôncavo'],
    'RUN': ['corrida','running','corredor','maratona','treinão','run club','atletismo','runner'],
}
EDITORIAS = ('Marketing', 'Plataformas', 'IA', 'Negócios', 'Creators', 'Brand+Creators', 'Marcas', 'Local', 'RUN')



def query_theme(area, cfg):
    query, hl, gl, ceid = cfg
    lookback = SECTION_LOOKBACK.get(area, 2)
    query = query + f' when:{lookback}d'
    max_age = dt.timedelta(days=lookback)
    url = 'https://news.google.com/rss/search?' + urlencode({'q':query,'hl':hl,'gl':gl,'ceid':ceid})
    output=[]
    try:
        res=requests.get(url,headers={'User-Agent':AGENT},timeout=17)
        res.raise_for_status()
        feed=feedparser.parse(res.content)
        for ent in feed.entries[:80]:
            parsed=ent.get('published_parsed') or ent.get('updated_parsed')
            if not parsed:
                continue
            published=dt.datetime.fromtimestamp(calendar.timegm(parsed),dt.timezone.utc)
            if published > NOW+dt.timedelta(hours=1) or NOW-published > max_age:
                continue
            title=clean(ent.get('title'))
            snippet=clean(ent.get('summary') or ent.get('description'))
            url_original=ent.get('link','')
            if not title or not url_original.startswith('https://'):
                continue
            words=(title+' '+snippet).lower()
            if any(b in words for b in BADWORDS) or not any(x in words for x in AREA_TERMS[area]):
                continue
            publisher=ent.get('source',{}).get('title') or 'Google Notícias (RSS)'
            publisher=clean(publisher)
            # links redistribuídos pelo Google Notícias são preservados.
            output.append({'id':hashlib.sha1(url_original.encode()).hexdigest()[:14],
                'area':area,'category':area,'title':title,'summary':snippet[:250],
                'source':publisher,'url':url_original,
                'published_at':published.astimezone(TZ).date().isoformat(),
                'published_utc':published.isoformat(),'language':'PT' if hl.startswith('pt') else 'EN',
                'score': 6 if (area in ('Local', 'RUN') and any(geo in words for geo in ('salvador', 'bahia', 'feira de santana', 'piaçabuçu', 'patamares', 'piatã'))) else 3, 'verification':'Manchete e resumo redistribuídos via RSS do Google Notícias; consulte a fonte original.',
                **({'image':entry_image(ent)} if entry_image(ent) else {})})
        print(f'Radar {area}: {len(output)} notícias encontradas')
    except Exception as exc:
        print('Radar indisponível:',area,str(exc)[:140],file=sys.stderr)
    return output


def prioritize_editorias(items):
    """Selecione até 20 itens relevantes por editoria, sem teto global e sem fabricação.

    Fontes com pouca cobertura podem entregar menos de 10. A meta editorial de 10
    não é usada para duplicar títulos, ampliar falsamente frescor nem gerar links.
    """
    output=[]
    seen_ids=set()
    for area in EDITORIAS:
        pool=[a for a in items if a.get('area',a.get('category'))==area]
        chosen=[]
        seen_titles=set()
        for a in pool:
            token=re.sub(r'[^a-z0-9]+','',a['title'].casefold())[:95]
            if a['id'] in seen_ids or token in seen_titles:
                continue
            # O score e a data são usados na ordem de coleta, para não preencher
            # automaticamente o máximo com notícias frágeis.
            chosen.append(a)
            seen_titles.add(token)
            seen_ids.add(a['id'])
            if len(chosen)>=MAX_PER_SECTION:break
        output.extend(chosen)
        print(f'Editoria {area}: {len(chosen)}/{MIN_PER_SECTION} meta; limite {MAX_PER_SECTION}')
    return output



def clean(raw):
    from html import unescape
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]*>', ' ', str(raw or '')))).strip()[:500]



def entry_image(ent):
    """Exibe imagem editorial fornecida pelo próprio feed quando disponibilizada.

    Não infere que a imagem seja de uma marca ou campanha específica.
    """
    candidates=[]
    for key in ('media_thumbnail','media_content'):
        for media in ent.get(key,[]) or []:
            if isinstance(media,dict):
                candidates.append(media.get('url',''))
    for media in ent.get('enclosures',[]) or []:
        if isinstance(media,dict) and (media.get('type','').startswith('image/') or media.get('medium')=='image'):
            candidates.append(media.get('href') or media.get('url') or '')
    for image in candidates:
        if isinstance(image,str) and image.startswith('https://'):
            return image[:1000]
    return None


def gather():
    collected=[]
    for outlet,url in FEEDS:
        try:
            res=requests.get(url,headers={'User-Agent':AGENT},timeout=22)
            res.raise_for_status()
            feed=feedparser.parse(res.content)
            if not feed.entries:
                print('Sem entradas:',outlet)
                continue
            for ent in feed.entries[:35]:
                t=ent.get('published_parsed') or ent.get('updated_parsed')
                if not t:
                    continue
                published=dt.datetime.fromtimestamp(calendar.timegm(t),dt.timezone.utc)
                if published > NOW + dt.timedelta(hours=1) or NOW-published > MAX_AGE:
                    continue
                title=clean(ent.get('title'))
                snippet=clean(ent.get('summary') or ent.get('description'))
                link=ent.get('link','')
                if not title or not link.startswith('https://'):
                    continue
                content=(' '+title+' '+snippet+' ').lower()
                if any(x in content for x in BADWORDS):
                    continue
                scores={c:sum(content.count(w) for w in words) for c,words in KEYWORDS.items()}
                score=max(scores.values())
                if score < 1:
                    continue
                category=max(scores,key=scores.get)
                digest=hashlib.sha1(link.encode()).hexdigest()[:14]
                collected.append({'id':digest,'category':category,'title':title,'summary':snippet[:250],
                                  'source':outlet,'url':link,'published_at':published.astimezone(TZ).date().isoformat(),
                                  'published_utc':published.isoformat(),'language':'EN','score':score,'area':category,
                                  **({'image':entry_image(ent)} if entry_image(ent) else {})})
            print('Feed OK:',outlet)
        except Exception as exc:
            print('Feed indisponível:',outlet,str(exc)[:140],file=sys.stderr)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures={pool.submit(query_theme,area,cfg):area for area,queries in THEME_QUERIES.items() for cfg in queries}
        for future in as_completed(futures):
            collected.extend(future.result())
    uniques={}
    for a in collected:
        key=re.sub('[^a-z0-9]','',a['title'].lower())[:65]
        if key not in uniques or a['score']>uniques[key]['score']:
            uniques[key]=a
    ranked=sorted(uniques.values(),key=lambda x:(x['score'],x['published_utc']),reverse=True)
    return prioritize_editorias(ranked)


def youtube_recent_hits():
    """Busca vídeos PUBLICADOS com fonte e métricas da API oficial do YouTube.

    A chave é opcional. Nunca chama qualquer vídeo de viral só por sua contagem
    absoluta de views; cada card registra visualizações e tempo desde a publicação.
    Busca em inglês para encontrar boas referências internacionais.
    """
    key=os.environ.get('YOUTUBE_API_KEY','').strip()
    if not key:
        print('Radar Internacional: YOUTUBE_API_KEY não configurada. Sem vídeos automáticos.')
        return []
    max_days=7  # Diferente das noticias: referência visual pode ter ciclo mais longo.
    published_after=(NOW-dt.timedelta(days=max_days)).isoformat().replace('+00:00','Z')
    video_queries=(
        'brand campaign behind the scenes',
        'creative advertising campaign 2026',
        'viral brand marketing commercial',
        'creator collaboration brand partnership',
        'short form video editing creative hook',
        'run club sports brand activation',
        'creative agency campaign case study',
        'new product launch branding design',
    )
    raw=[]
    for query in video_queries:
        try:
            res=requests.get('https://www.googleapis.com/youtube/v3/search',params={
                'part':'snippet','q':query,'type':'video','order':'date',
                'publishedAfter':published_after,'maxResults':15,
                'relevanceLanguage':'en','key':key}, timeout=17)
            res.raise_for_status()
            raw.extend(res.json().get('items',[]))
        except (requests.RequestException, ValueError) as exc:
            print('YouTube indisponível:', query, str(exc)[:160],file=sys.stderr)
    by_id={x.get('id',{}).get('videoId'):x for x in raw if x.get('id',{}).get('videoId')}
    if not by_id:
        print('Radar Internacional: API respondeu sem vídeos válidos.')
        return []
    ids=list(by_id)
    details=[]
    for start in range(0,len(ids),50):
        try:
            res=requests.get('https://www.googleapis.com/youtube/v3/videos',params={
                'part':'statistics,snippet,status','id':','.join(ids[start:start+50]),'key':key}, timeout=17)
            res.raise_for_status()
            details.extend(res.json().get('items',[]))
        except (requests.RequestException, ValueError) as exc:
            print('Dados de vídeo indisponíveis:',str(exc)[:160],file=sys.stderr)
    results=[]
    for video in details:
        try:
            if video.get('status',{}).get('privacyStatus','public')!='public':continue
            date=dt.datetime.fromisoformat(video['snippet']['publishedAt'].replace('Z','+00:00'))
            hours=(NOW-date).total_seconds()/3600
            if not (0<hours<max_days*24):continue
            views=int(video.get('statistics',{}).get('viewCount','0'))
            if views<2500:continue
            rate=round(views/max(2,hours)*24)
            vid=video['id']
            if not re.fullmatch(r'[A-Za-z0-9_-]{11}',vid):continue
            title=clean(video['snippet']['title'])
            if not title:continue
            thumb=video['snippet'].get('thumbnails',{}).get('high',{}).get('url','')
            channel=clean(video['snippet'].get('channelTitle',''))
            results.append({'title':title,'url':'https://www.youtube.com/watch?v='+vid,
                'platform':'YouTube','language':'EN','published_at':date.date().isoformat(),
                'source':channel,'views':views,'views_per_day':rate,
                'verification':'Dados públicos de visualização via YouTube Data API. Não comprova viralidade.',
                'insight':f'{views:,} visualizações públicas; aproximadamente {rate:,} por 24h desde a publicação. Observe gancho, edição e linguagem da campanha.',
                'image':thumb if thumb.startswith('https://') else ''})
        except (KeyError,TypeError,ValueError):
            continue
    results.sort(key=lambda v:(v['views_per_day'],v['views']),reverse=True)
    print('Radar Internacional:',len(results),'vídeos analisados,',min(20,len(results)),'selecionados')
    return results[:MAX_PER_SECTION]


def social_videos():
    """Conecta posts verificados manualmente, nunca converte artigos em virais."""
    file=ROOT/'config'/'virais.json'
    try:
        items=json.loads(file.read_text(encoding='utf-8'))
    except Exception:
        return []
    out=[]
    for a in items:
        try:
            url=a['url'];host=urlparse(url).netloc.lower()
            date=dt.date.fromisoformat(a['published_at'])
            age=dt.datetime.combine(date,dt.time(0),TZ)
            if not any(host==h or host.endswith('.'+h) for h in ('youtube.com','youtu.be','instagram.com','tiktok.com')):
                continue
            if a.get('verified') is not True or not 0 <= (NOW.astimezone(TZ)-age).total_seconds() <= 72*3600:
                continue
            out.append({'title':clean(a.get('title','Post em observação')),'url':url,'platform':a.get('platform','Social'),
                        'language':a.get('language','EN'),'insight':clean(a.get('insight','Conteúdo original para analisar.')),
                        'image':a.get('image','') if str(a.get('image','')).startswith('https://') else ''})
        except (TypeError,ValueError,KeyError):
            continue
    return out[:20]


def ai_editorial(news):
    key=os.environ.get('OPENAI_API_KEY','').strip()
    if not key:
        return None
    brief=[{k:a[k] for k in ('id','title','summary','source','category','published_at','area')} for area in EDITORIAS for a in [x for x in news if x.get('area')==area][:2]]
    candidates=[{'id':a['id'],'area':a.get('area',a.get('category')),'title':a['title'],'published_at':a['published_at'],'source':a['source']} for a in news]
    instruction="""Você é um editor brasileiro de notícias de negócios para o SINAL, publicação SOMMOS ALTUM. Use SOMENTE dados fornecidos de título/resumo de feeds, não matérias completas. NUNCA fabrique eventos, números, afirmações, URLs ou métricas sociais. Responda SOMENTE JSON válido com as chaves selected_ids_by_area, articles, ideas, opportunity e signal.
selected_ids_by_area: objeto mapeando CADA editora ao ARRAY COMPLETO dos IDs relevantes, em ordem de prioridade. Quando houver 10 ou mais candidatos confiáveis de uma editoria, escolha DE 10 A 20 IDs, não só os dois destaques. Se houver menos que 10 fontes úteis, selecione menos; não invente. Use o array all_candidates_for_selection para selecionar, não apenas featured_for_writing. Selecione 10-20 IDs por editoria de maneira independente, nunca apenas 10-20 no jornal inteiro.
articles: objetos com id, title, summary, why e action SOMENTE para os poucos destaques em featured_for_writing. São análises complementares, e o código PRESERVA os títulos/resumos exatos do feed para tradução subsequente. Não transforme valores monetários: US$100.000 e R$100.000 não são equivalentes. Preserve quantias, países, nomes e datas.
ideas: exatamente 3 ideias executáveis e reais, cada uma com campos: title (título direto), project (SOMENTE o nome da marca escolhida entre SOMMOS ALTUM, Migo Telemedicina, Corre Cristão, MOOV, LEÇAI, ou "Aplicação geral"), description (proposta específica), objective (resultado que se quer testar), steps (array de 3 a 5 passos acionáveis, específicos e factíveis em até um dia), deliverable (entrega concreta do dia), metric (um indicador mensurável), source_id (id verdadeiro de uma notícia em featured_for_writing que inspirou o teste). Não invente campanhas, parcerias ou funcionalidades. Importante: MOOV e Corre Cristão são projetos de corrida, Migo Telemedicina é de saúde, LEÇAI é produto de açaí e SOMMOS ALTUM é agência de estratégia e comunicação. NUNCA escreva "MOOV Telemedicina". Quando a notícia for apenas contexto, apresente a ideia como hipótese para experimentar, não fato comprovado. opportunity: title, description, tag. signal: texto com hipótese explícita.
Em textos de why/action, diferencie teste de lançamento, hipótese de fato, ressalve fonte secundária, evite fatos não verificados. Conecte ações a Corre Cristão, MOOV, Migo Telemedicina, SOMMOS ALTUM ou LEÇAI quando pertinente. Sem notícias pesadas. Uma manchete de RSS não comprova o artigo inteiro."""
    payload={"model":os.environ.get('OPENAI_MODEL','gpt-4.1-mini'),"input":[{"role":"system","content":instruction},{"role":"user","content":json.dumps({"featured_for_writing":brief,"all_candidates_for_selection":candidates,"limits":{"target_min":MIN_PER_SECTION,"max":MAX_PER_SECTION}},ensure_ascii=False)}],"text":{"format":{"type":"json_object"}}}
    try:
        response=requests.post('https://api.openai.com/v1/responses',json=payload,
                               headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},timeout=110)
        response.raise_for_status()
        result=response.json()
        raw=result.get('output_text')
        if not raw:
            raw=''.join(part.get('text','') for item in result.get('output',[]) for part in item.get('content',[]) if part.get('type')=='output_text')
        obj=json.loads(raw)
        if not isinstance(obj.get('articles'),list) or not isinstance(obj.get('ideas'),list):
            raise ValueError('Curadoria incompleta')
        print('Curadoria com IA concluída.')
        return obj
    except Exception as exc:
        print('IA indisponível. Aplicando curadoria básica:',str(exc)[:180],file=sys.stderr)
        return None


def default_issue(news):
    items=[]
    for a in news:
        item={k:v for k,v in a.items() if k not in ('score','published_utc')}
        item['summary']=a['summary'] or 'Nova publicação da fonte indicada sobre este tema. Leia a matéria original para conferir os detalhes.'
        item['why']='Este assunto apareceu na janela de monitoramento. A relevância para sua operação depende do conteúdo completo da fonte e do seu público.'
        item['action']='Leia a fonte original e anote uma pergunta que seu público faria sobre o assunto. Use essa pergunta como ponto de partida para um conteúdo.'
        item['verification']='Manchete e resumo de feed RSS; sem verificação do artigo integral.'
        items.append(item)
    ideas=[
        {'title':'Pergunta vira conteúdo','project':'SOMMOS ALTUM','description':'Escolha uma notícia do radar e transforme uma pergunta real do público em conteúdo útil.','objective':'Testar se uma resposta curta interessa ao público.','steps':['Selecione uma notícia com fonte e uma dúvida que seu público faz sobre o tema.','Escreva um roteiro com gancho, resposta concreta e convite para conversar; grave um vídeo de até 30 segundos.','Publique ou teste internamente e anote retenção e respostas recebidas.'],'deliverable':'Um roteiro e um vídeo piloto de até 30 segundos.','metric':'Retenção do vídeo e respostas relevantes.'},
        {'title':'Teste duas aberturas','project':'MOOV','description':'Compare duas aberturas de vídeo sobre uma experiência de corrida.','objective':'Avaliar qual gancho gera atenção inicial.','steps':['Escolha um único assunto do evento e um público-alvo definido.','Prepare dois ganchos diferentes mantendo iguais as demais cenas; grave as duas versões.','Teste com grupo pequeno e registre comentários e intenção de participar.'],'deliverable':'Dois roteiros e dois cortes curtos.','metric':'Retenção inicial e respostas do público.'},
        {'title':'Uma objeção, uma resposta','project':'Migo Telemedicina','description':'Transforme uma objeção real em uma explicação clara, sem prometer resultados ou cobertura não verificada.','objective':'Reduzir dúvidas antes do contato comercial.','steps':['Anote a dúvida mais repetida recebida pela equipe.','Crie uma resposta em linguagem simples, confirmando todos os benefícios e condições com a oferta vigente.','Publique um story ou encaminhe a peça para avaliação e acompanhe perguntas recebidas.'],'deliverable':'Um texto de resposta e um story de teste.','metric':'Dúvidas qualificadas e solicitações de informação.'}
    ]
    return {'articles':items,'ideas':ideas,'opportunity':{'title':'Informação recente pode virar experimento de venda',
            'description':'Selecione a descoberta mais relevante da edição, formule uma hipótese e teste uma única mudança na campanha ou na oferta antes de escalar.',
            'tag':'HIPÓTESE / VALIDAR COM SEUS DADOS'},
            'signal':'Os temas em alta no radar sugerem perguntas novas do consumidor. Hipótese editorial: conteúdo que responde essas perguntas cedo pode ganhar atenção, sem garantia de alcance.'}


def build_issue(news, edited):
    source_by_id={a['id']:a for a in news}
    base=default_issue(news)
    if edited:
        articles=[]
        for item in edited.get('articles',[]):
            a=source_by_id.get(item.get('id'))
            if not a or a['id'] in [x['id'] for x in articles]:
                continue
            verified={k:v for k,v in a.items() if k not in ('score','published_utc')}
            # Títulos e resumos permanecem exatamente como vieram do RSS até a
            # tradução final. A análise da IA não pode trocar US$ por R$, mudar
            # números, aumentar certezas ou acrescentar fatos na manchete.
            for key in ('why', 'action'):
                val=item.get(key)
                if isinstance(val,str) and val.strip():
                    verified[key]=val.strip()[:480]
            verified['verification']='Curadoria baseada em manchete e resumo do RSS; consulte a fonte original.'
            articles.append(verified)
        if articles:
            # Não descarte notícias verificadas só porque a IA escolheu poucos
            # destaques para enriquecer. O editorial mantém a seleção inteira.
            enriched_by_id={a['id']:a for a in articles}
            base['articles']=[enriched_by_id.get(a['id'],a) for a in base['articles']]
        if len(edited.get('ideas',[]))==3:
            base['ideas']=[x for x in edited['ideas'] if isinstance(x,dict)][:3]
        if isinstance(edited.get('opportunity'),dict):
            base['opportunity']=edited['opportunity']
        if isinstance(edited.get('signal'),str):
            base['signal']=edited['signal']
    # A IA participa da decisão editorial sobre QUANTOS entram em cada área.
    # Só pode escolher IDs que foram realmente encontrados nos feeds; nunca cria links.
    if edited and isinstance(edited.get('selected_ids_by_area'),dict):
        selections=edited['selected_ids_by_area']
        per_area={area:[a for a in base['articles'] if a.get('area',a.get('category'))==area] for area in EDITORIAS}
        selected=[]
        for area in EDITORIAS:
            pool=per_area[area]
            ids=selections.get(area)
            if not isinstance(ids,list) or not ids:
                selected.extend(pool[:MAX_PER_SECTION])
                continue
            wanted={id for id in ids if isinstance(id,str)}
            matched=[a for a in pool if a['id'] in wanted][:MAX_PER_SECTION]
            # Uma IA que recebeu dois destaques para redação NÃO pode restringir
            # a editoria inteira a dois itens. Se ela devolver menos de dez
            # IDs e a curadoria RSS já selecionou dez fontes com data e URL,
            # complete SOMENTE com esse conjunto verificado, sem criar notícia.
            target=min(MIN_PER_SECTION,len(pool))
            if len(matched)<target:
                known={a['id'] for a in matched}
                for candidate in pool:
                    if candidate['id'] not in known:
                        matched.append(candidate)
                        known.add(candidate['id'])
                    if len(matched)>=target:
                        break
            selected.extend(matched[:MAX_PER_SECTION])
            print(f'Seleção {area}: {len(matched[:MAX_PER_SECTION])} notícias (RSS elegíveis: {len(pool)})')
        base['articles']=selected

    try:
        prior=json.loads((DATA/'archive'/'index.json').read_text(encoding='utf-8'))
        existing_dates=[e.get('date') for e in prior.get('editions',[])]
    except Exception:
        existing_dates=[]
    highlights=[]
    for area in EDITORIAS:
        article=next((a for a in base['articles'] if a.get('area',a.get('category'))==area),None)
        highlights.append({'area':area,'article_id':article['id'] if article else None,'status':'verified_feed' if article else 'awaiting_source'})
    issue={
        'highlights':highlights,
        'edition_date':TODAY,'generated_at':NOW.isoformat(),
        'edition_number':len(set(existing_dates+[TODAY])),
        'edition_note':f'Notícias de até {LOOKBACK} horas; cases de marcas, criadores, local e RUN podem ter janelas de 7 a 14 dias, indicadas pela data; interpretações editoriais são hipóteses.',
        'section_policy':{'min_target':MIN_PER_SECTION,'max_per_section':MAX_PER_SECTION,'no_filler':True,'case_windows_days':SECTION_LOOKBACK},
        'section_counts':{area:sum(1 for a in base['articles'] if a.get('area',a.get('category'))==area) for area in EDITORIAS},
        'articles':base['articles'],'virals':list({x['url']:x for x in (social_videos()+youtube_recent_hits())}.values())[:MAX_PER_SECTION],
        'ideas':base['ideas'],'opportunity':base['opportunity'],'signal':base['signal']
    }
    return issue




def _openai_json_with_retry(instruction, input_data, key, attempts=3):
    """Solicita JSON estruturado sem tornar tradução parcial uma edição válida."""
    payload = {
        'model': os.environ.get('OPENAI_MODEL', 'gpt-4.1-mini'),
        'input': [
            {'role': 'system', 'content': instruction},
            {'role': 'user', 'content': json.dumps(input_data, ensure_ascii=False)}
        ],
        'text': {'format': {'type': 'json_object'}}
    }
    last = None
    for n in range(attempts):
        try:
            response = requests.post(
                'https://api.openai.com/v1/responses', json=payload,
                headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
                timeout=120
            )
            response.raise_for_status()
            result = response.json()
            raw = result.get('output_text') or ''.join(
                part.get('text', '')
                for item in result.get('output', [])
                for part in item.get('content', [])
                if part.get('type') == 'output_text'
            )
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError('Resposta não é objeto JSON')
            return data
        except (requests.RequestException, ValueError, KeyError) as exc:
            last = exc
            if n < attempts - 1:
                time.sleep(2 ** n)
    raise RuntimeError(f'Falha na tradução via API após {attempts} tentativas: {last}')


def translate_issue_ptbr(issue):
    """Traduz TODAS as manchetes, resumos, banners e vídeos exibidos no SINAL.

    A tradução ocorre APÓS a curadoria de links, para que nenhum artigo selecionado
    fique em inglês por não estar entre os destaques. Não altera links ou métricas.
    Falha fechada: se a API não estiver disponível, a edição anterior é preservada.
    """
    key = os.environ.get('OPENAI_API_KEY', '').strip()
    if not key:
        raise RuntimeError(
            'OPENAI_API_KEY ausente. Cadastre a chave em GitHub Settings > Secrets and variables > Actions. '
            'Não será publicada edição nova com manchetes em inglês.'
        )
    tasks = []
    originals = {}
    for article in issue.get('articles', []):
        uid = 'a:' + str(article['id'])
        fields = {name: article[name] for name in ('title', 'summary', 'banner_title')
                  if isinstance(article.get(name), str) and article[name].strip()}
        if fields:
            tasks.append({'id': uid, 'texts': fields})
            originals[uid] = article
    for i, video in enumerate(issue.get('virals', [])):
        uid = f'v:{i}'
        fields = {name: video[name] for name in ('title', 'insight')
                  if isinstance(video.get(name), str) and video[name].strip()}
        if fields:
            tasks.append({'id': uid, 'texts': fields})
            originals[uid] = video

    if not tasks:
        return issue

    instruction = """Você é um tradutor editorial brasileiro do jornal SINAL, de marketing,
negócios e tecnologia. Sua missão é garantir que TODOS os textos públicos recebidos
estejam em português do Brasil natural, claro e profissional. Traduza manchetes,
resumos e destaques do inglês ao português. Se um texto já estiver em português,
apenas conserve ou ajuste a fluência sem mudar os fatos. NÃO escreva fatos novos,
não invente números, não aumente certezas nem transforme testes em lançamentos.
Preserve nomes próprios, marcas, siglas técnicas, números e qualificações relevantes.
PRESERVE RIGOROSAMENTE UNIDADES MONETÁRIAS: nunca traduza $ ou US$ como R$.
Se o original indicar dólares americanos, use US$ ou mantenha o símbolo $;
NUNCA converta valores, moedas, datas ou unidades sem instrução explícita.
Quando aparecer $100,000, a forma portuguesa pode ser US$ 100 mil, NUNCA R$ 100 mil.
Resuma apenas quando necessário para manter fluência; não use frases em inglês nem
marcas de tradução. Ignore trechos promocionais genéricos de RSS como 'The post ...
appeared first on ...' sem perder fatos essenciais. Não inclua opinião ou
interpretação não presente no original. Traduza 'banner_title' também, quando existir.
Responda ESTRITAMENTE em JSON: {"items":[{"id":"id original", "texts":
{"title":"...", "summary":"...", "banner_title":"...", "insight":"..."}}]}.
Cada item recebido deve ter o MESMO id e exatamente as chaves recebidas em texts.
NÃO repita links, não modifique IDs e não adicione itens."""
    batch_size = 12
    groups = [tasks[i:i+batch_size] for i in range(0, len(tasks), batch_size)]
    collected = {}
    print('Tradução PT-BR: iniciando', len(tasks), 'itens em', len(groups), 'lotes')

    def handle_batch(batch):
        data = _openai_json_with_retry(instruction, {'items': batch}, key)
        values = data.get('items')
        if not isinstance(values, list):
            raise RuntimeError('Resposta da tradução sem array items')
        expected = {x['id']: set(x['texts']) for x in batch}
        output = {}
        for translated in values:
            if not isinstance(translated, dict):
                continue
            uid = translated.get('id')
            fields = translated.get('texts')
            if uid not in expected or not isinstance(fields, dict):
                continue
            if not all(isinstance(fields.get(k), str) and fields[k].strip() for k in expected[uid]):
                continue
            # Tamanho de proteção contra saída fora de escopo; nada é traduzido em tela pelo JS.
            output[uid] = {k: fields[k].strip()[:450] for k in expected[uid]}
        if set(output) != set(expected):
            raise RuntimeError('Tradução incompleta: IDs/colunas não retornados pela IA')
        return output

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(handle_batch, batch) for batch in groups]
        for future in as_completed(futures):
            collected.update(future.result())
    if len(collected) != len(tasks):
        raise RuntimeError('Tradução incompleta; edição anterior mantida')

    for uid, fields in collected.items():
        item = originals[uid]
        for name, translated in fields.items():
            original = item[name]
            if original != translated:
                item['original_' + name] = original
            item[name] = translated
        item['source_language'] = item.get('language', 'indefinido')
        item['language'] = 'PT'
        item['display_language'] = 'pt-BR'
        item['translation_status'] = 'traduzido_ou_revisado_por_ia'
    issue['display_language'] = 'pt-BR'
    print('Tradução concluída:', len(tasks), 'itens em português (Brasil).')
    return issue

class _OpenGraphParser(HTMLParser):
    """Lê apenas meta OG/Twitter de uma página HTML (não o corpo da matéria)."""
    def __init__(self):
        super().__init__()
        self.images=[]
    def handle_starttag(self,tag,attrs):
        if tag!='meta':return
        d=dict(attrs)
        attr=(d.get('property') or d.get('name') or '').lower()
        if attr in ('og:image:secure_url','og:image','twitter:image','twitter:image:src'):
            self.images.append(d.get('content','').strip())


def _safe_external_url(raw):
    try:
        parsed=urlparse(str(raw))
        host=(parsed.hostname or '').lower()
        if parsed.scheme!='https' or not host or parsed.username or parsed.password:
            return False
        if host=='localhost' or host.endswith(('.local','.internal')) or host in ('news.google.com',):
            return False
        try:
            ip=ipaddress.ip_address(host)
            return ip.is_global
        except ValueError:
            return '.' in host
    except (ValueError,TypeError):
        return False


def _article_image_from_publisher(article):
    url=article.get('url','')
    if not _safe_external_url(url):
        return None
    try:
        res=requests.get(url,headers={'User-Agent':AGENT,'Accept':'text/html'},
                         timeout=8,stream=True,allow_redirects=False)
        if res.status_code!=200 or 'text/html' not in res.headers.get('Content-Type',''):
            res.close();return None
        # No redirects to internal URLs and no unbounded downloads.
        raw=b''
        for chunk in res.iter_content(chunk_size=8192):
            raw+=chunk
            if len(raw)>160_000:break
        res.close()
        parser=_OpenGraphParser()
        parser.feed(raw.decode('utf-8','replace'))
        for found in parser.images:
            candidate=urljoin(url,found)
            if _safe_external_url(candidate):
                return candidate[:1000]
    except (requests.RequestException, UnicodeError, ValueError) as exc:
        print('Imagem de fonte indisponível:',article.get('source',''),str(exc)[:75],file=sys.stderr)
    return None


def add_editorial_images(issue):
    """Tenta imagem de publisher nos destaques e cards iniciais.

    O fallback visual atual do site continua quando o veículo não disponibiliza
    metadados, bloqueia a leitura ou não permite hotlink. Imagem NÃO é prova
    de autoria/endorso; manter crédito e abrir a matéria original.
    """
    articles=issue.get('articles',[])
    for a in articles:
        if a.get('image') and _safe_external_url(a['image']):
            a['image_origin']='rss'
        elif a.get('image'):
            a.pop('image',None)
    candidates=[]
    # Primeiro todos os banners, depois 2 cards adicionais por editoria.
    for area in EDITORIAS:
        pool=[a for a in articles if a.get('area',a.get('category'))==area and not a.get('image')]
        candidates.extend(pool[:3])
    # Evitar 100 requests e reduzir latência em publicação diária.
    candidates=candidates[:30]
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures={pool.submit(_article_image_from_publisher,a):a for a in candidates}
        for f in as_completed(futures):
            article=futures[f]
            image=f.result()
            if image:
                article['image']=image
                article['image_origin']='publisher_og'
    print('Imagens editoriais reais:',sum(bool(a.get('image')) for a in articles),
          'de',len(articles),'matérias; restante utiliza ilustrações locais.')
    return issue


def write_issue(issue):
    path=DATA/'archive'/f'{TODAY}.json'
    content=json.dumps(issue,indent=2,ensure_ascii=False)+'\n'
    path.write_text(content,encoding='utf-8')
    (DATA/'latest.json').write_text(content,encoding='utf-8')
    (DATA/'bootstrap.js').write_text('window.BOOTSTRAP_EDITION = '+json.dumps(issue,separators=(',',':'),ensure_ascii=False)+';\n',encoding='utf-8')
    index_path=DATA/'archive'/'index.json'
    try:
        index=json.loads(index_path.read_text(encoding='utf-8'))
        entries=index.get('editions',[])
    except Exception:
        entries=[]
    entries=[e for e in entries if e.get('date')!=TODAY]
    entries.insert(0,{'date':TODAY,'label':dt.date.fromisoformat(TODAY).strftime('%d/%m/%Y'),
                      'path':f'data/archive/{TODAY}.json'})
    index_path.write_text(json.dumps({'editions':entries[:366]},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Edição salva:',TODAY,'matérias:',len(issue['articles']),'virais:',len(issue['virals']))


def main():
    if not os.environ.get('OPENAI_API_KEY','').strip():
        raise RuntimeError('Falta OPENAI_API_KEY nos segredos do GitHub Actions para tradução automática PT-BR. Edição anterior preservada.')
    news=gather()
    if len(news)<3:
        print('Menos de 3 itens recentes com fonte. Edição anterior preservada.',file=sys.stderr)
        return 0
    edited=ai_editorial(news)
    issue=build_issue(news,edited)
    issue=translate_issue_ptbr(issue)
    issue=add_editorial_images(issue)
    write_issue(issue)
    return 0

if __name__=='__main__':
    sys.exit(main())
