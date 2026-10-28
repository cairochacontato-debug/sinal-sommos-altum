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
from urllib.parse import urlparse, urlencode
from zoneinfo import ZoneInfo

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
SECTION_LOOKBACK = {'Marcas':14, 'Local':14, 'RUN':7, 'Creators':7, 'Brand+Creators':14}  # estudos e casos têm ciclos mais longos
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
        ('Salvador Bahia empresa inauguração expansão restaurante cafeteria negócios', 'pt-BR','BR','BR:pt'),
        ('Bahia marcas regionais empreendedorismo comércio varejo lojas', 'pt-BR','BR','BR:pt')],
    'RUN': [
        ('corrida de rua treinão running club maratona Salvador Bahia Brasil', 'pt-BR','BR','BR:pt'),
        ('running brands run club race activation sport event', 'en-US','US','US:en')],
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
                'score': 3, 'verification':'Manchete e resumo redistribuídos via RSS do Google Notícias; consulte a fonte original.',
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
    """Opcional: utiliza YouTube Data API para medir visualizações públicas recentes.

    Uma taxa alta de visualizações é apenas sinal observado, não comprovação
    de que o vídeo 'viralizou' ou que terá o mesmo resultado no Brasil.
    """
    key=os.environ.get('YOUTUBE_API_KEY','').strip()
    if not key:
        return []
    published_after=(NOW-MAX_AGE).isoformat().replace('+00:00','Z')
    candidates=[]
    for query in ('brand marketing campaign', 'creative video ads'):
        try:
            response=requests.get('https://www.googleapis.com/youtube/v3/search',params={
                'part':'snippet','q':query,'type':'video','order':'viewCount',
                'publishedAfter':published_after,'maxResults':12,'relevanceLanguage':'en','key':key
            },timeout=20)
            response.raise_for_status()
            candidates.extend(response.json().get('items',[]))
        except Exception as exc:
            print('YouTube indisponível:',str(exc)[:140],file=sys.stderr)
    candidates_by_id={x.get('id',{}).get('videoId'):x for x in candidates if x.get('id',{}).get('videoId')}
    if not candidates_by_id:
        return []
    try:
        response=requests.get('https://www.googleapis.com/youtube/v3/videos',params={
            'part':'statistics,snippet','id':','.join(candidates_by_id.keys()),'key':key
        },timeout=20)
        response.raise_for_status()
        items=response.json().get('items',[])
    except Exception as exc:
        print('Estatísticas YouTube indisponíveis:',str(exc)[:140],file=sys.stderr)
        return []
    hits=[]
    for v in items:
        try:
            date=dt.datetime.fromisoformat(v['snippet']['publishedAt'].replace('Z','+00:00'))
            elapsed=max(1,(NOW-date).total_seconds()/3600)
            views=int(v.get('statistics',{}).get('viewCount','0'))
            rate=views*24/elapsed
            if views<20000 or rate<10000 or elapsed>48:
                continue
            title=clean(v['snippet']['title'])
            url='https://www.youtube.com/watch?v='+v['id']
            hits.append({'title':title,'url':url,'platform':'YouTube','language':'EN',
                         'insight':f'{views:,} visualizações públicas em aproximadamente {elapsed:.0f} horas; sinal de tração, não comprovação de viralidade. Analise o gancho e adapte a ideia ao contexto brasileiro.',
                         'image':v.get('snippet',{}).get('thumbnails',{}).get('high',{}).get('url','')})
        except (KeyError,TypeError,ValueError):
            continue
    hits.sort(key=lambda x:int(re.search(r'[0-9,]+',x['insight']).group(0).replace(',','')),reverse=True)
    return hits[:20]


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
    instruction="""Você é um editor brasileiro de notícias de negócios para um jornal privado chamado SINAL, uma publicação SOMMOS ALTUM. Use SOMENTE os dados fornecidos; são título/resumo de feeds, NÃO matérias completas. NUNCA fabrique eventos, números, afirmações ou exemplos virais. Responda SOMENTE JSON válido com chaves: selected_ids_by_area (objeto com arrays de IDs confiáveis agrupados por categoria, com 10 a 20 selecionados por editoria quando houver candidatos úteis; pode selecionar menos de 10 se faltarem evidências e NUNCA invente IDs), articles (array de objetos com id, title, summary, why, action), ideas (EXATAMENTE 3 objetos com title, project, description), opportunity (title, description, tag), signal (texto). Artigos: enriqueça os destaques fornecidos por editoria, preservando IDs. Você está redigindo apenas destaques, NÃO restringindo o número de matérias no site. O sistema publica 10 a 20 fontes distintas por editoria quando houver evidência suficiente, inclusive Brand+Creators; em cada summary até 280 caracteres; why e action até 380 caracteres, em linguagem natural. Diferencie teste de lançamento, hipótese de fato, e adote ressalvas para fonte secundária. Garanta conexão das ações aos projetos Corre Cristão, MOOV, Migo Telemedicina, SOMMOS ALTUM, LEÇAI. Opportunity deve ser hipótese de negócio, não notícia inventada. O signal precisa ser explicitamente hipótese, não certeza. Sem notícias pesadas. Uma reportagem pode ser apenas sugestão de oportunidade, não confirmação do fato original."""
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
        {'title':'Pergunta vira conteúdo','project':'MIGO / SOMMOS ALTUM','description':'Escolha uma notícia do radar, identifique uma dúvida real do público e transforme a resposta em vídeo de 30 segundos.'},
        {'title':'Teste duas aberturas','project':'CORRE CRISTÃO / MOOV','description':'Grave duas versões curtas do mesmo assunto e compare os sinais de retenção e compartilhamento, sem presumir viralidade.'},
        {'title':'Uma objeção, uma resposta','project':'LEÇAI / MIGO','description':'Crie uma peça de venda respondendo à objeção mais frequente e direcione o público para um canal de compra simples.'}
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
            for key in ('title','summary','why','action'):
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
            # Não imponha dez por preenchimento se a IA desconsiderou itens fracos.
            if matched:
                selected.extend(matched)
            else:
                selected.extend(pool[:MAX_PER_SECTION])
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
    news=gather()
    if len(news)<3:
        print('Menos de 3 itens recentes com fonte. Edição anterior preservada.',file=sys.stderr)
        return 0
    edited=ai_editorial(news)
    issue=build_issue(news,edited)
    write_issue(issue)
    return 0

if __name__=='__main__':
    sys.exit(main())
