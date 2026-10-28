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
MAX_TOTAL_NEWS = 40  # limite GLOBAL de notícias por edição (não por editoria)
MAX_CANDIDATES_PER_AREA = 18  # candidatos para a curadoria, nunca cota de publicação
MAX_PER_SECTION = 20  # apenas limite de vídeos; notícia usa AREAS_CAPS
AREAS_CAPS = {'Marketing': 8, 'Plataformas': 8, 'IA': 6, 'Negócios': 5,
              'Creators': 4, 'Brand+Creators': 5, 'Marcas': 4,
              'Local': 4, 'RUN': 7, 'Saúde': 6}
MIN_RELEVANCE_SCORE = 5  # notícia sem aplicação direta não entra para completar cota
SECTION_LOOKBACK = {'Marcas':10, 'Local':7, 'RUN':10, 'Creators':7, 'Brand+Creators':10, 'Saúde':7}  # estudos e casos têm ciclos mais longos
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
    'Saúde': ['telehealth','telemedicine','healthtech','digital health','benefits healthcare','mental health at work'],
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
        ('marketing performance ads attribution conversion rate case study', 'en-US','US','US:en'),
        ('tráfego pago meta ads google ads conversão campanha resultados', 'pt-BR','BR','BR:pt'),
        ('marketing creative testing A/B landing page CRO email retention', 'en-US','US','US:en')],
    'Plataformas': [
        ('instagram reels new features video update creators meta ads', 'en-US','US','US:en'),
        ('instagram tiktok youtube novas funções anúncios algoritmo', 'pt-BR','BR','BR:pt'),
        ('meta ads manager google ads youtube shorts business update', 'en-US','US','US:en')],
    'IA': [
        ('AI agent automation workflow tool marketing business product update', 'en-US','US','US:en'),
        ('inteligência artificial ferramentas agentes automação empresas', 'pt-BR','BR','BR:pt')],
    'Negócios': [
        ('ecommerce retail subscriptions growth strategy conversion case study', 'en-US','US','US:en'),
        ('pequenos negócios varejo ecommerce assinaturas estratégia vendas', 'pt-BR','BR','BR:pt')],
    'Creators': [
        ('creator economy monetization short form video strategy audience retention', 'en-US','US','US:en'),
        ('criador conteúdo monetização UGC formato vídeos marketing', 'pt-BR','BR','BR:pt')],
    'Brand+Creators': [
        ('creator brand partnership UGC case study advertising performance', 'en-US','US','US:en'),
        ('campanha marcas creators UGC embaixadores estratégia resultado', 'pt-BR','BR','BR:pt')],
    'Marcas': [
        ('brand repositioning product launch customer experience case study', 'en-US','US','US:en'),
        ('rebranding marca reposicionamento inovação experiência cliente case', 'pt-BR','BR','BR:pt')],
    'Local': [
        ('(inauguração OR expande OR franquia) (Salvador OR Bahia) empresa loja', 'pt-BR','BR','BR:pt'),
        ('(restaurante OR cafeteria OR varejo) (Salvador OR Bahia) estratégia expansão', 'pt-BR','BR','BR:pt'),
        ('(marca OR startup) baiana (lançamento OR expansão OR inovação)', 'pt-BR','BR','BR:pt')],
    'RUN': [
        ('corrida de rua marcas patrocínio experiência comunidade Brasil', 'pt-BR','BR','BR:pt'),
        ('treinão gratuito running club corrida de rua marcas Brasil', 'pt-BR','BR','BR:pt'),
        ('corrida de rua organização evento inscrições percurso Brasil', 'pt-BR','BR','BR:pt'),
        ('running community brand activation race event sponsorship', 'en-US','US','US:en'),
        ('maratona corrida marketing esportivo ativações comunidade', 'pt-BR','BR','BR:pt')],
    'Saúde': [
        ('telemedicina saúde digital empresas plano benefício colaboradores', 'pt-BR','BR','BR:pt'),
        ('saúde mental trabalho NR-1 riscos psicossociais empresas', 'pt-BR','BR','BR:pt'),
        ('healthtech telehealth mental health at work employer benefits', 'en-US','US','US:en'),
        ('telemedicina psicologia nutrição plataforma regulamentação mercado Brasil', 'pt-BR','BR','BR:pt')]
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
    'RUN': ['corrida de rua','running','maratona','treinão','run club','atletismo','runner','patrocínio esportivo','meia maratona'],
    'Saúde': ['telemedicina','telemedicine','telehealth','saúde digital','healthtech','saúde mental','mental health','psicologia','nr-1','riscos psicossociais','benefício saúde','health benefits'],
}
EDITORIAS = ('Marketing', 'Plataformas', 'IA', 'Negócios', 'Creators', 'Brand+Creators', 'Marcas', 'Local', 'RUN', 'Saúde')



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
            if any(b in (' '+title.lower()+' ') for b in BADWORDS) or not any(x in words for x in AREA_TERMS[area]):
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


# Curadoria 7.0: o assunto precisa oferecer uma mudança, tática ou caso reproduzível.
# Não é um classificador médico: apenas filtra notícias do mercado, sem prescrever condutas.
STOP_TOPICS = re.compile(r'\b(?:anitta|virginia\s+fonseca|lu[ií]sa\s+sonza|bbb|big\s+brother|famos[ao]s?|celebridade|namorad[oa]|casamento|div[oó]rcio|fofoca|trai[cç][aã]o|hor[oó]scopo|astrologia|morreu|morte|homic[ií]dio|assalto|pol[ií]cia|inc[eê]ndio|apag[aã]o|interrup[cç][aã]o\s+de\s+energia|acidente|terras\s+raras|elei[cç][oõ]es|receita\s+bilion[aá]ria|resultados\s+trimestrais|earnings\s+call)\b', re.I)
BUSINESS_TRIGGERS = ('lança','lançamento','launch','test','testa','nova função','new feature','update','atualiz','algorit','anúnc','ads','tráfego','convers','conversion','ctr','cpc','cpa','roas','performance','ferrament','tool','workflow','autom','automat','agent','agente','aplic','estrat','strategy','como','how','case study','estudo de caso','experi','experience','resultado','growth','cresci','patroc','parceria','partnership','monetiz','rebrand','reposicion','campanha','campaign','experimento','a/b','funil','landing page','reten','retention','mídia','media buying','mensura','attribution','attribution','crm','e-commerce','ecommerce','loja','expans','subscription','assinatura','inscri','engajamento','engagement','social commerce','marketplace','comunidade','community','nr-1','psicossoc','regulament','compliance','telemed','healthtech')
RUN_CONTEXT = ('corrida de rua','corridas de rua','maratona','meia maratona','running','run club','running club','treinão','treinao','corredor','atletismo','atleta','prova de corrida','race','5 km','10 km','21 km','42 km','5k','10k','patrocínio esportivo')
RUN_UTILITY = ('marca','brand','experiência','experi','organiza','inscri','evento','event','calendário','kit','patroc','ativa','comunidade','community','clube','club','marketing','trein','percurso','hidrata','logística','particip','recorde de inscrição','modelo','negócio','negocio','format','campanha','venda','engaja','acesso','gratuit','nova prova','lança')
LOCAL_BUSINESS = ('empresa','negócio','negocio','loja','startup','franquia','inaugura','restaurante','cafeteria','varejo','marca','ecommerce','e-commerce','comércio','comercio','expans','empreend','vendas','atendimento','experiência','experiencia','cliente','lançamento','mercado','food service')
HEALTH_MARKET = ('telemedicina','telemedicine','telehealth','saúde digital','saude digital','healthtech','health tech','saúde mental','saude mental','mental health','nr-1','psicossocial','psicologia','psicólogo','psicologo','nutrição','nutricao','benefício saúde','beneficio saude','saúde corporativa','saude corporativa','plano de saúde','plano de saude','medicina digital','regulação de saúde','consulta online','medtech')
HEALTH_UTILITY = ('empresa','trabalho','corporat','colaborador','funcion','benefício','beneficio','regul','nr-1','mercado','plataforma','telemed','saúde digital','saude digital','healthtech','cobertura','atendimento','produto','psicossocial','programa','modelo','custo','acesso','expansão','expansao','lançamento','implementa','segurança','compliance')


def normalized_terms(text):
    import unicodedata
    plain=unicodedata.normalize('NFKD',str(text or '').lower())
    plain=''.join(c for c in plain if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+',' ',plain).strip()


def near_duplicate(first, second):
    # Somente títulos comparáveis, evitando cinco manchetes do mesmo evento.
    common={'de','do','da','dos','das','em','na','no','com','para','por','o','a','e','um','uma','the','new','and','for','in','to','com','2026','2027','que','sobre'}
    x=set(normalized_terms(first).split())-common
    y=set(normalized_terms(second).split())-common
    if not x or not y:return False
    return len(x&y)/len(x|y) >= .64 or (len(x&y)>=5 and len(x&y)/min(len(x),len(y))>=.83)


def relevance_score(a):
    area=a.get('area',a.get('category',''))
    title=normalized_terms(a.get('title',''))
    desc=normalized_terms(a.get('summary',''))[:300]
    full=title+' '+desc
    if STOP_TOPICS.search(full) or any(k in full for k in ('ganhou na loteria','ficou noiva','foi preso','festa de aniversario','vazou video intimo')):return 0
    # Bancos de notícias generalistas indexam acidentes, fofocas e apostas: não são sinais aplicáveis.
    if area=='Local':
        if not any(x in full for x in ('salvador','bahia','baiana','baiano','feira de santana','recôncavo','bahi')):return 0
        if not any(x in full for x in LOCAL_BUSINESS):return 0
        if not any(x in full for x in ('inaugur','expans','lanç','nova','novo','modelo','estrat','invest','mercado','franquia','marca','varejo','negócio','negocio','empresa','experiência','atendimento','vendas','tendência','rede')):return 0
    if area=='RUN':
        if not any(x in full for x in RUN_CONTEXT):return 0
        if not any(x in full for x in RUN_UTILITY):return 0
        if any(x in full for x in ('corrida eleitoral','corrida por','corrida ao','corrida presidencial','corrida espacial','corrida armamentista','maratona de shows','maratona de filmes','maratona de lives')):return 0
    if area=='Saúde':
        if not any(x in full for x in HEALTH_MARKET):return 0
        if not any(x in full for x in HEALTH_UTILITY):return 0
    if area in ('Marketing','Plataformas','IA','Negócios','Creators','Brand+Creators','Marcas'):
        # Uma pessoa ou empresa famosa não basta. É necessário método, ferramenta ou mudança concreta.
        if not any(x in full for x in BUSINESS_TRIGGERS):return 0
        if area=='Negócios' and not any(x in full for x in ('negócio','negocio','business','ecommerce','e commerce','retail','varejo','startup','convers','vendas','assinatura','subscription','estrat','marketing','empreend','cliente','franquia','growth','loja','commercial','commerce','pricing','preço','preco','receita por','lucro por')):return 0
        if area=='Marcas' and not any(x in full for x in ('marca','brand','rebrand','branding','reposicion','campanha','design','lança','launch','experiência','experience','cliente','cresci','expans','estrat')):return 0
    strong=('lança','testa','nova função','atualização','anúncios','ads','tráfego','conversão','meta ads','google ads','criativo','performance','estratégia','case study','estudo de caso','integra','automat','agentes','workflow','brand activation','run club','corrida de rua','patrocínio','benefícios','nr-1','telemedicina','rebranding','ux','cro','captação','mensuração')
    s=2+sum(min(2,title.count(normalized_terms(w))) for w in strong)+min(3,sum(1 for w in BUSINESS_TRIGGERS if normalized_terms(w) in full))
    if area=='RUN':s+=2
    if area=='Saúde':s+=2
    if area=='Plataformas' and any(w in title for w in ('instagram','meta ads','tiktok','youtube','google ads')):s+=2
    if area=='Local':s+=2
    if a.get('source') in ('Search Engine Journal','Social Media Today','Marketing Dive'):s+=1
    return s


def prioritize_editorias(items):
    output=[]; seen_ids=set(); seen_titles=[]
    for area in EDITORIAS:
        pool=[]
        for candidate in items:
            if candidate.get('area',candidate.get('category'))!=area:continue
            score=relevance_score(candidate)
            if score<MIN_RELEVANCE_SCORE:continue
            candidate['editorial_score']=score
            pool.append(candidate)
        pool.sort(key=lambda a:(a['editorial_score'],a.get('score',0),a.get('published_utc','')), reverse=True)
        chosen=[]
        for a in pool:
            if a['id'] in seen_ids or any(near_duplicate(a['title'],t) for t in seen_titles):continue
            seen_ids.add(a['id']);seen_titles.append(a['title']);chosen.append(a)
            if len(chosen)>=MAX_CANDIDATES_PER_AREA:break
        output.extend(chosen)
        print(f'Editoria {area}: {len(chosen)} candidatos acionáveis, ainda NÃO publicados')
    return output


def select_global_40(news, edited):
    # A IA pode rejeitar notícias fracas; nunca preencher o restante com fofocas.
    chosen_by_id={a['id']:a for a in news if relevance_score(a)>=MIN_RELEVANCE_SCORE}
    ranking=[]
    if edited:
        ids=edited.get('selected_ids')
        if isinstance(ids,list):ranking=[str(v) for v in ids if isinstance(v,str)]
        if not ranking and isinstance(edited.get('selected_ids_by_area'),dict):
            ranking=[i for area in EDITORIAS for i in edited['selected_ids_by_area'].get(area,[]) if isinstance(i,str)]
    if ranking:
        accepted=[chosen_by_id[i] for i in ranking if i in chosen_by_id]
        # Caso o modelo só devolva 2 destaques, usar o filtro determinístico.
        if len(accepted)<10 and len(chosen_by_id)>=20:accepted=list(chosen_by_id.values())
    else:accepted=list(chosen_by_id.values())
    accepted=list({a['id']:a for a in accepted}.values())
    # Sem resposta da IA, priorizar relevância; com IA, combinar posição e score.
    if not ranking or len(ranking)<10:
        accepted.sort(key=lambda a:(a.get('editorial_score',relevance_score(a)),a.get('published_utc','')),reverse=True)
    groups={k:[] for k in EDITORIAS}
    for a in accepted:
        area=a.get('area',a.get('category'))
        if area in groups:groups[area].append(a)
    out=[];counts={a:0 for a in EDITORIAS};seen_titles=[]
    def take(a):
        area=a.get('area',a.get('category'))
        if counts.get(area,0)>=AREAS_CAPS[area] or any(near_duplicate(a['title'],b) for b in seen_titles):return False
        out.append(a);seen_titles.append(a['title']);counts[area]+=1;return True
    # Dar espaço inicial a cada nicho disponível, sem reservar vagas vazias.
    for n in range(2):
        for area in EDITORIAS:
            if len(out)>=MAX_TOTAL_NEWS:break
            pool=groups[area]
            if len(pool)>n:take(pool[n])
    # Completar por relevância e prioridade do modelo até no máximo 40.
    rest=[a for a in accepted if a['id'] not in {b['id'] for b in out}]
    for a in rest:
        if len(out)>=MAX_TOTAL_NEWS:break
        take(a)
    assert len(out)<=MAX_TOTAL_NEWS
    print(f'Curadoria SINAL 7.0: {len(out)}/{MAX_TOTAL_NEWS} notícias realmente úteis (teto global).',counts)
    return out


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
                if any(x in (' '+title.lower()+' ') for x in BADWORDS):
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
        'official brand advertising campaign 2026 case study',
        'brand campaign creative commercial 2026',
        'creator x brand collaboration campaign 2026',
        'meta ads creative performance case study',
        'brand running club activation race marketing',
        'brand new product launch creative campaign 2026',
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
            if views<5000:continue
            rate=round(views/max(2,hours)*24)
            vid=video['id']
            if not re.fullmatch(r'[A-Za-z0-9_-]{11}',vid):continue
            title=clean(video['snippet']['title'])
            description=clean(video['snippet'].get('description',''))
            if not title:continue
            # Radar não é tutorial genérico, gossip, opinião esportiva ou renda fácil.
            if STOP_TOPICS.search(title+' '+description):continue
            vt=normalized_terms(title)
            vd=normalized_terms(description)
            good=('campaign','commercial','advertising','ad creative','brand activation',
                  'brand collaboration','brand partnership','campaign breakdown',
                  'case study','ad campaign','marketing strategy','brand launch',
                  'running club','social media campaign','meta ads','creative testing')
            if not any(x in vt or x in vd for x in good):continue
            if any(x in vt for x in ('tutorial','make money','how to get rich','get rich','reaction','drama','learn in 20','million dollars a month')):continue
            if rate<900:continue
            thumb=video['snippet'].get('thumbnails',{}).get('high',{}).get('url','')
            channel=clean(video['snippet'].get('channelTitle',''))
            results.append({'title':title,'url':'https://www.youtube.com/watch?v='+vid,
                'platform':'YouTube','language':'EN','published_at':date.date().isoformat(),
                'source':channel,'views':views,'views_per_day':rate,
                'verification':'Dados públicos de visualização via YouTube Data API. Não comprova viralidade.',
                'insight':f'{views:,} visualizações públicas; média estimada de {rate:,} visualizações por 24h desde a publicação. Analise o gancho, a oferta e a execução criativa; este número não comprova conversão.',
                'image':thumb if thumb.startswith('https://') else ''})
        except (KeyError,TypeError,ValueError):
            continue
    results.sort(key=lambda v:(v['views_per_day'],v['views']),reverse=True)
    print('Radar Internacional:',len(results),'vídeos analisados,',min(20,len(results)),'selecionados')
    return results[:12]


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
    if not key:return None
    # A IA só recebe manchetes realmente coletadas; nunca pode inventar notícia.
    candidates=[{'id':a['id'],'area':a.get('area'), 'title':a['title'],
                 'summary':a.get('summary','')[:175], 'published_at':a['published_at'],
                 'source':a['source'],'editorial_score':a.get('editorial_score',0)} for a in news]
    instruction="""Você é o editor-chefe do SINAL 7.0, jornal de inteligência APLICÁVEL, 100% em português brasileiro.
Seu leitor é um estrategista que opera agências de marketing e branding, marcas e e-commerce,
eventos de corrida de rua no Brasil, além de uma empresa de telemedicina (Migo).
Não interessa vida de pessoas, famosos, Anitta, entretenimento, gossip, resultados de futebol,
política genérica, crimes, notícia local geral, empreendedorismo vago, resultados financeiros
sem método, nem corridas como metáfora ou notícia genérica sobre competição.
Prioridade absoluta: mudanças REALMENTE aplicáveis na Meta Ads, Google Ads, Instagram,
TikTok, YouTube, formatos e distribuição, CTR/CAC/ROAS, IA para fluxos de trabalho,
criativos de anúncios, casos replicáveis de marcas, ativações de running clubs e corridas
em TODO O BRASIL, telemedicina, saúde corporativa, psicologia, NR-1 e saúde digital
somente quando exista mudança operacional/comercial verificável.
Cada item selecionado deve ter uma consequência prática e explicável: 'O que posso testar
amanhã, qual decisão isso afeta, qual métrica observar?'. Se não souber responder,
EXCLUA. Classifique novidades TESTADAS como teste, não como função já liberada.
Use SOMENTE títulos e resumos fornecidos; nunca invente dados, previsões, impactos,
recursos lançados, eficácia clínica, datas, percentuais ou regulamentações.
Responda JSON rigoroso com: selected_ids (array de ATÉ 40 IDs encontrados, em ordem de
relevância prática, sem duplicações), ideas (exatamente 3), opportunity, signal.
Não precisa atingir 40; entre menos conteúdo e conteúdo fraco, escolha menos.
No máximo 8 por tema. Há 10 editorias. Equilibre oportunidades, sem forçar quotas.
As 3 ideias devem se inspirar em uma notícia selecionada, incluir cada uma:
title, project (uma destas marcas: SOMMOS ALTUM, Migo Telemedicina, Corre Cristão,
MOOV, LEÇAI ou Aplicação geral), description, objective, steps (3-5 ações específicas
factíveis em um dia), deliverable, metric e source_id (ID verdadeiro escolhido).
Escolha preferencialmente uma estratégia de marketing/plataforma, uma de RUN e uma
para a Migo, se houver fonte relevante nesses nichos; nunca invente casos.
Migo TELEMEDICINA NÃO É MOOV, que é a corrida. Não misture marcas.
A experiência de corrida pode se beneficiar de marcas, comunidade, percurso, inscrições,
patrocínios, patamares, conteúdo, captação e retenção. Em telemedicina priorize
acesso, aquisição, benefício para empregadores e comunicação ética, sem promessas médicas.
Ideias não são fatos, explicite hipótese e teste antes de escala.
opportunity: title,description,tag com oportunidade aplicável.
signal: hipótese fraca, não afirmar tendência confirmada sem dados.
Mantenha marcas, datas, preços, valores e moedas como na fonte.
Responda JSON, sem markdown."""
    payload={'model':os.environ.get('OPENAI_MODEL','gpt-4.1-mini'),
      'input':[{'role':'system','content':instruction},{'role':'user','content':json.dumps({
         'edition_goal':'até 40 notícias de alto valor prático NO TOTAL, não por editoria',
         'candidate_articles':candidates},ensure_ascii=False)}],
      'text':{'format':{'type':'json_object'}}}
    try:
        response=requests.post('https://api.openai.com/v1/responses',json=payload,
            headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},timeout=120)
        response.raise_for_status()
        result=response.json()
        raw=result.get('output_text') or ''.join(x.get('text','') for item in result.get('output',[]) for x in item.get('content',[]) if x.get('type')=='output_text')
        obj=json.loads(raw)
        if not isinstance(obj.get('selected_ids'),list):raise ValueError('IA não retornou selected_ids')
        print('Curadoria com IA concluída:',len(obj['selected_ids']),'IDs solicitados; validação e teto de 40 serão aplicados.')
        return obj
    except Exception as exc:
        print('IA de seleção indisponível. Aplicando curadoria de regras:',str(exc)[:180],file=sys.stderr)
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
    selected=select_global_40(news, edited)
    base=default_issue(selected)
    if edited:
        valid_ideas=[]
        for idea in edited.get('ideas',[]) if isinstance(edited.get('ideas'),list) else []:
            if not isinstance(idea,dict):continue
            if not all(isinstance(idea.get(k),str) and idea[k].strip() for k in ('title','project','description','objective','deliverable','metric')):continue
            steps=idea.get('steps')
            if not isinstance(steps,list) or len([x for x in steps if isinstance(x,str) and x.strip()])<3:continue
            item={k:idea[k] for k in ('title','project','description','objective','deliverable','metric')}
            item['steps']=[x[:400].strip() for x in steps if isinstance(x,str) and x.strip()][:5]
            sid=idea.get('source_id')
            if isinstance(sid,str) and sid in {a['id'] for a in selected}:item['source_id']=sid
            valid_ideas.append(item)
        if len(valid_ideas)==3:base['ideas']=valid_ideas
        if isinstance(edited.get('opportunity'),dict):base['opportunity']=edited['opportunity']
        if isinstance(edited.get('signal'),str):base['signal']=edited['signal']
    try:
        prior=json.loads((DATA/'archive'/'index.json').read_text(encoding='utf-8'))
        existing_dates=[e.get('date') for e in prior.get('editions',[])]
    except Exception:existing_dates=[]
    highlights=[]
    for area in EDITORIAS:
        article=next((a for a in base['articles'] if a.get('area',a.get('category'))==area),None)
        highlights.append({'area':area,'article_id':article['id'] if article else None,
          'status':'verified_feed' if article else 'awaiting_source'})
    return {
        'highlights':highlights,'edition_date':TODAY,'generated_at':NOW.isoformat(),
        'edition_number':len(set(existing_dates+[TODAY])),
        'edition_note':'Até 40 sinais acionáveis no total. A IA pode selecionar menos; não usamos notícias fracas para preencher vagas. Datas e fontes identificadas.',
        'section_policy':{'edition_cap':MAX_TOTAL_NEWS,'min_per_section':0,'no_filler':True,
          'actionable_only':True,'case_windows_days':SECTION_LOOKBACK},
        'section_counts':{a:sum(1 for x in base['articles'] if x.get('area',x.get('category'))==a) for a in EDITORIAS},
        'articles':base['articles'],
        'virals':list({x['url']:x for x in (social_videos()+youtube_recent_hits())}.values())[:12],
        'ideas':base['ideas'],'opportunity':base['opportunity'],'signal':base['signal']}


def enrich_actions_ptbr(issue):
    """Explica a decisão e o teste prático para CADA uma das até 40 notícias, sem criar fatos."""
    key=os.environ.get('OPENAI_API_KEY','').strip()
    items=issue.get('articles',[])
    if not items:return issue
    instruction="""Você é um editor de inteligência aplicada do SINAL. Gere em português brasileiro
EXATAMENTE dois campos para CADA notícia recebida, sem inventar fatos:
why: 1-2 frases específicas que expliquem o impacto operacional/comercial, com base SOMENTE
na manchete/resumo; condicional para testes/rumores, jamais afirmar efeito ou causalidade
não demonstrada.
action: roteiro concreto de experimento em 1-3 passos para uma operação de
marketing/tráfego, e-commerce, marca, corrida nacional ou Migo Telemedicina;
inclua o QUE fazer, COMO testar e QUAL métrica acompanhar. Nunca recomendar
prática médica individual, diagnóstico nem alegar atendimento clínico sem respaldo.
Nunca atribua aumento de conversão, volume de vendas ou efeito clínico sem dados.
Não mude títulos, IDs, números, moedas nem nomes; não cite notícias que não recebeu.
Retorne JSON {"items":[{"id":"id exato","why":"...","action":"..."}]}.
Todos os IDs devem ser devolvidos, sem faltantes."""
    groups=[items[i:i+8] for i in range(0,len(items),8)]
    def process(batch):
        request={'items':[{'id':a['id'],'title':a['title'],'summary':a['summary'][:260],
              'area':a.get('area'),'source':a['source']} for a in batch]}
        response=_openai_json_with_retry(instruction,request,key,attempts=2)
        result=response.get('items',[])
        expected={a['id'] for a in batch};mapping={}
        for r in result:
            if isinstance(r,dict) and r.get('id') in expected and all(isinstance(r.get(k),str) and r[k].strip() for k in ('why','action')):
                mapping[r['id']]={'why':r['why'].strip()[:460],'action':r['action'].strip()[:560]}
        if set(mapping)!=expected:raise RuntimeError('IA retornou plano incompleto para as notícias')
        return mapping
    all_results={}
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures=[pool.submit(process,b) for b in groups]
            for future in as_completed(futures):all_results.update(future.result())
    except Exception as exc:
        # Não inventar uma estratégia como se fosse derivada da matéria; retorno neutro.
        print('Análise individual indisponível, usando instrução explícita de validação:',str(exc)[:120],file=sys.stderr)
        return issue
    for a in items:
        a.update(all_results[a['id']])
        a['analysis_type']='hipotese_estrategica_fundamentada_em_rss'
    print('Estratégias práticas geradas para',len(items),'notícias.')
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
    candidates=candidates[:32]
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
    issue=enrich_actions_ptbr(issue)
    issue=translate_issue_ptbr(issue)
    issue=add_editorial_images(issue)
    write_issue(issue)
    return 0

if __name__=='__main__':
    sys.exit(main())
