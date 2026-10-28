(() => {
  const $ = (id) => document.getElementById(id);
  const state = {edition:window.BOOTSTRAP_EDITION || {articles:[],virals:[],ideas:[]},filter:'Todos',search:'',saved:readSaved(),current:'latest',activeBanner:0,bannerPaused:false,visibleArticles:6,visibleVirals:6};
  const fmt = new Intl.DateTimeFormat('pt-BR',{day:'numeric',month:'long',year:'numeric',timeZone:'America/Bahia'});
  const weekdayFmt = new Intl.DateTimeFormat('pt-BR',{weekday:'long',day:'numeric',month:'long',timeZone:'America/Bahia'});
  const safe = (s) => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const safeUrl = (u) => /^https:\/\//i.test(String(u || '')) ? safe(u) : '#';
  const PHOTO_BASE = 'assets/editorial/';
  const editorialPhotos = ['filmmaker','branding','editing','creator','tech','workspace','studio','cafe','runners'];
  const imageFor=(a,i=0)=>{
    const provided=String(a?.image||'');
    if (/^https:\/\//i.test(provided)) return safeUrl(provided);
    const title=String(a?.title||'').toLowerCase();
    let local;
    if (/tiktok/.test(title)) local='creator';
    else if (/edits|assistência por ia|inteligência artificial|\bia\b/.test(title)) local='tech';
    else if (/séries de reels|links de séries|encadeado/.test(title)) local='editing';
    else if (/instagram|vídeos horizontais/.test(title)) local='filmmaker';
    else if (/linkedin/.test(title)) local='studio';
    else if (/meta|campanha|anúnc|brand/.test(title)) local='branding';
    else local=editorialPhotos[i%editorialPhotos.length];
    return PHOTO_BASE+local+'.webp';
  };
  const imageTag=(a,i,cl='')=>`<img class="${cl}" src="${imageFor(a,i)}" alt="${/^https:\/\//i.test(String(a?.image||''))?'Imagem disponibilizada pela fonte: ':'Imagem ilustrativa relacionada à matéria: '}${safe(a.title||'')}" loading="lazy" referrerpolicy="no-referrer" onerror="this.onerror=null;this.src='assets/editorial/workspace.webp';this.alt='Imagem ilustrativa relacionada à matéria'" />`;
  const excerpt=(s,n=130)=>{s=String(s||'');return s.length>n?s.slice(0,n).trim().replace(/\s+\S*$/,'')+'…':s;};
  const prettyDate = (s) => {const d = new Date((s||'2026-10-28')+'T12:00:00-03:00');return Number.isNaN(d.getTime())?'Data a confirmar':fmt.format(d)};
  function readSaved(){try{return JSON.parse(localStorage.getItem('aristoteles-saved')||'[]')}catch{return []}}
  function persist(){try{localStorage.setItem('aristoteles-saved',JSON.stringify(state.saved))}catch{}}
  function toast(t){const e=$('toast');e.textContent=t;e.classList.add('visible');clearTimeout(toast.t);toast.t=setTimeout(()=>e.classList.remove('visible'),2400)}
  const categories = {Marketing:'MARKETING',Plataformas:'PLATAFORMAS',IA:'INTELIGÊNCIA ARTIFICIAL',Negócios:'NEGÓCIOS',Creators:'CREATORS',Marcas:'MARCAS EM MOVIMENTO',Local:'NEGÓCIOS LOCAIS',RUN:'RUN','Brand+Creators':'BRAND + CREATORS'};
  const badge = (a) => safe(categories[a.category] || a.category || 'MOVIMENTO');
  function render(){
    const issue=state.edition;
    const d=issue.edition_date||'2026-10-28';
    $('headerDate').textContent=weekdayFmt.format(new Date(d+'T12:00:00-03:00')).toUpperCase();
    const n=String(issue.edition_number||1).padStart(3,'0');
    $('topEdition').textContent=`EDIÇÃO DIGITAL • Nº ${n}`;
    const freshness=issue.edition_note||`EDIÇÃO DE ${prettyDate(d).toUpperCase()}`;
    $('freshness').textContent=state.current==='latest'?`EDIÇÃO DE ${prettyDate(d).toUpperCase()}`:`ARQUIVO • ${prettyDate(d).toUpperCase()}`;
    $('freshness').title=freshness;
    $('footerUpdated').textContent=`ATUALIZADO EM ${prettyDate(d).toUpperCase()}`;
    $('savedCount').textContent=state.saved.length?`(${state.saved.length})`:'';
    renderBanners();renderLead();renderNews();renderVirals();renderIdeas();renderInsights();
  }
  // Uma imagem + uma notícia com procedência por editoria. Se não há fonte, exibe estado de curadoria.
  const BANNER_AREAS=[
    {key:'Marketing',label:'MARKETING',photo:'branding',anchor:'manchetes',subtitle:'Campanhas e estratégias'},
    {key:'Plataformas',label:'PLATAFORMAS',photo:'filmmaker',anchor:'manchetes',subtitle:'Redes, distribuição e alcance'},
    {key:'IA',label:'INTELIGÊNCIA ARTIFICIAL',photo:'tech',anchor:'manchetes',subtitle:'Ferramentas e transformações'},
    {key:'Negócios',label:'NEGÓCIOS',photo:'workspace',anchor:'manchetes',subtitle:'Movimentos do mercado'},
    {key:'Creators',label:'CREATORS',photo:'creator',anchor:'creators',subtitle:'Quem está criando agora'},
    {key:'Brand+Creators',label:'BRAND + CREATORS',photo:'studio',anchor:'collabs',subtitle:'Campanhas e colaborações de marca'},
    {key:'Marcas',label:'RISING BRANDS',photo:'studio',anchor:'brands',subtitle:'Marcas para estudar'},
    {key:'Local',label:'NEGÓCIOS LOCAIS',photo:'cafe',anchor:'local',subtitle:'Salvador e Bahia em destaque'},
    {key:'RUN',label:'SINAL RUN',photo:'runners',anchor:'run',subtitle:'Corridas, marcas e comunidades'}
  ];
  const exactBannerArea=(a,area)=> a.area === area || (!a.area && a.category===area);
  function bannersForIssue(){
    const articles=state.edition.articles||[];
    const defined=Array.isArray(state.edition.highlights)?state.edition.highlights:[];
    return BANNER_AREAS.map(cfg=>{
      const metadata=defined.find(x=>x.area===cfg.key)||{};
      // A presença de um ID válido impede banners com notícias inventadas.
      const article=articles.find(x=>x.id===metadata.article_id) || articles.find(x=>exactBannerArea(x,cfg.key));
      return {...cfg,article,metadata};
    });
  }
  function renderBanners(){
    const issue=state.edition, banners=bannersForIssue();
    const index=Math.min(Math.max(state.activeBanner,0),banners.length-1);state.activeBanner=index;
    const b=banners[index], a=b.article;
    const fallbackImage='assets/editorial/'+b.photo+'.webp';
    const sourceImage=a?imageFor(a,index):fallbackImage;
    const hasSource=a && /^https:\/\//i.test(String(a.image||''));
    const headline=a ? (a.banner_title || excerpt(a.title,65)) : 'Ainda sem notícia recente verificada nesta área.';
    const kicker=a ? `${safe(a.source)} · ${safe(prettyDate(a.published_at))}`:'MONITORAMENTO ATIVO · AGUARDANDO FONTE';
    const action=a ? `<button type="button" data-open="${safe(a.id)}" class="banner-cta">Entenda o movimento <span>↗</span></button>`:`<a class="banner-cta" href="#${safe(b.anchor)}">Explorar ${safe(b.label.toLowerCase())} <span>↗</span></a>`;
    $('dailyBanner').innerHTML=`<div class="banner-visual" style="background-image:linear-gradient(90deg,rgba(10,15,29,.95) 0%,rgba(10,15,29,.86) 37%,rgba(10,15,29,.40) 72%,rgba(10,15,29,.10) 100%),url('${safe(sourceImage)}')"></div><div class="banner-glow"></div><div class="banner-content"><span class="banner-kicker"><span class="banner-live-dot"></span> DESTAQUE ${String(index+1).padStart(2,'0')} / ${String(banners.length).padStart(2,'0')} · ${safe(b.label)}</span><span class="banner-meta">${kicker}</span><h2>${safe(headline)}</h2><p>${a?safe(excerpt(a.summary,115)):safe(b.subtitle+'. O SINAL ainda não encontrou matéria publicada e verificável na janela editorial.')}</p><div class="banner-actions">${action}<span class="banner-image-note">${hasSource?'IMAGEM DA FONTE':'IMAGEM ILUSTRATIVA'}</span></div></div><div class="banner-index-watermark" aria-hidden="true">0${index+1}</div>`;
    $('bannerPosition').textContent=`${String(index+1).padStart(2,'0')} / ${String(banners.length).padStart(2,'0')}`;
    $('showcaseEdition').textContent=(issue.edition_date||'').split('-').reverse().join('.') || 'EDIÇÃO ATUAL';
    $('bannerTopics').innerHTML=banners.map((x,i)=>`<button type="button" class="banner-topic ${i===index?'is-active':''}" data-banner-index="${i}" aria-label="Mostrar destaque: ${safe(x.label)}" aria-current="${i===index?'true':'false'}"><span class="topic-thumb"><img src="assets/editorial/${x.photo}.webp" alt="" loading="lazy"></span><span>${safe(x.label)}</span><i aria-hidden="true">${x.article?'●':'○'}</i></button>`).join('');
  }
  function selectBanner(next,manual=true){
    state.activeBanner=(next+BANNER_AREAS.length)%BANNER_AREAS.length;
    renderBanners();
    if(manual){state.bannerPaused=true; syncBannerPlayButton();}
  }
  function syncBannerPlayButton(){
    $('bannerAutoplay').textContent=state.bannerPaused?'▶':'Ⅱ';
    $('bannerAutoplay').setAttribute('aria-label',state.bannerPaused?'Retomar rotação automática':'Pausar rotação automática');
  }
  function renderLead(){
    const a=state.edition.articles||[];
    if(!a.length){$('featureCard').innerHTML='<h3>Uma edição está sendo preparada.</h3><p>As matérias aparecerão quando fontes verificadas estiverem disponíveis.</p>';$('leadSide').innerHTML='';return}
    const top=a[0];
    $('featureCard').innerHTML=`<div class="feature-photo">${imageTag(top,0)}</div><div class="feature-scrim"></div><div class="feature-content"><span class="visual-kicker">${badge(top)} <span>· CAPA</span></span><h3>${safe(top.title)}</h3><div class="feature-footer"><span class="news-source">${safe(top.source)} · ${safe(prettyDate(top.published_at))}</span><button type="button" data-open="${safe(top.id)}" aria-label="Ler análise completa">Ler história ↗</button></div></div>`;
    $('leadSide').innerHTML=a.slice(1,3).map((x,i)=>`<article class="mini-card"><div class="mini-photo">${imageTag(x,i+1)}</div><div class="mini-scrim"></div><div class="mini-inner"><div class="mini-top"><span class="visual-kicker">${badge(x)}</span><button type="button" data-save="${safe(x.id)}" aria-label="${state.saved.includes(x.id)?'Remover dos salvos':'Salvar matéria'}">${state.saved.includes(x.id)?'★':'☆'}</button></div><h3>${safe(x.title)}</h3><div class="mini-footer"><span>${safe(x.source)}</span><button type="button" data-open="${safe(x.id)}">Ler ↗</button></div></div></article>`).join('');
  }
  function matching(){const articles=state.edition.articles||[];return articles.filter(a=>{
    const matchesCategory=state.filter==='Todos'||state.filter==='Salvos'&&state.saved.includes(a.id)||(a.area||a.category)===state.filter;
    const hay=[a.title,a.summary,a.source,a.category,a.action,a.why].join(' ').toLocaleLowerCase('pt-BR');
    return matchesCategory && hay.includes(state.search.toLocaleLowerCase('pt-BR'));
  });}
  function renderNews(){
    const all=matching();
    const articles=state.filter==='Todos' && !state.search ? all.slice(3):all;
    const showing=articles.slice(0,state.visibleArticles);
    $('resultCount').textContent=`${articles.length} ${articles.length===1?'MATÉRIA':'MATÉRIAS'}`;
    if(state.filter==='Todos' || state.filter==='Salvos') {
      $('sectionCoverage').textContent=`${Math.min(articles.length,state.visibleArticles)} de ${articles.length} matérias nesta seleção. Explore as editorias pelo menu para ver a cobertura completa.`;
    } else {
      const label=categories[state.filter]||state.filter;
      $('sectionCoverage').textContent=articles.length<10
        ? `${label}: ${articles.length} conteúdos disponíveis nesta edição. A meta é encontrar 10 a 20, sem duplicar ou inventar notícias.`
        : `${label}: ${articles.length} notícias e análises selecionadas nesta edição. Exibindo ${Math.min(articles.length,state.visibleArticles)}.`;
    }
    $('moreNews').hidden=articles.length<=state.visibleArticles;
    $('moreNews').textContent=`Mostrar mais ${Math.min(6,articles.length-state.visibleArticles)} de ${articles.length} ↓`;
    $('newsGrid').innerHTML=showing.map((a,i)=>`<article class="news-card"><div class="news-media">${imageTag(a,i+3)}<div class="news-media-top"><span class="category-chip">${badge(a)}</span><button class="save-overlay" type="button" data-save="${safe(a.id)}" aria-label="${state.saved.includes(a.id)?'Remover dos salvos':'Salvar matéria'}">${state.saved.includes(a.id)?'★':'☆'}</button></div></div><div class="news-body"><h3>${safe(a.title)}</h3><p>${safe(excerpt(a.summary,120))}</p><div class="news-card-bottom"><span>${safe(a.source)}</span><button type="button" data-open="${safe(a.id)}">Abrir ↗</button></div></div></article>`).join('');
    $('emptyState').hidden=articles.length>0;
  }
  function renderVirals(){
    const virals=state.edition.virals||[];
    if(virals.length){$('viralCoverage').textContent=`${virals.length} referências verificadas na edição. Meta de 10 a 20, conforme fontes disponíveis.`;$('moreVirals').hidden=virals.length<=state.visibleVirals; $('moreVirals').textContent=`Ver mais ${Math.min(6,virals.length-state.visibleVirals)} referências ↓`;$('viralCards').innerHTML=virals.slice(0,state.visibleVirals).map((v,i)=>`<article class="viral-card"><div class="viral-media">${imageTag(v,i+1)}<span class="video-play" aria-hidden="true">▶</span></div><div class="viral-card-copy"><div class="type">${safe(v.platform||'VÍDEO')} / ORIGEM ${safe(v.source_language||v.language||'EN')}</div><h3>${safe(v.title)}</h3><p>${safe(excerpt(v.insight,145))}</p><a href="${safeUrl(v.url)}" target="_blank" rel="noopener noreferrer">Ver publicação original ↗</a></div></article>`).join('');return;}
    $('moreVirals').hidden=true; $('viralCoverage').textContent='Nenhum vídeo internacional com URL verificada nesta edição; não são criados links fictícios.';
    const examples=[['filmmaker','Ganchos e narrativas','Observe como um vídeo abre a conversa.'],['editing','Edição e ritmo','Repare em cortes, tempo e enquadramento.'],['studio','Marcas e criadores','Como uma campanha ganha linguagem própria.']];
    $('viralCards').innerHTML=examples.map(x=>`<article class="viral-card example-card"><div class="viral-media"><img src="assets/editorial/${x[0]}.webp" loading="lazy" alt="Imagem ilustrativa de conteúdo criativo"/><span class="video-play" aria-hidden="true">✦</span></div><div class="viral-card-copy"><div class="type">FORMATO PARA ESTUDAR · DEMONSTRAÇÃO</div><h3>${x[1]}</h3><p>${x[2]}</p></div></article>`).join('')+`<p class="viral-note">Imagens conceituais para demonstrar o layout. Esta edição não contém vídeos virais verificados; quando forem encontrados, os cartões terão link direto para o conteúdo original.</p>`;
  }
  function renderIdeas(){
    const imgs=['runners','creator','branding'];
    $('ideasGrid').innerHTML=(state.edition.ideas||[]).slice(0,3).map((x,i)=>`<article class="idea-card"><div class="idea-media"><img src="assets/editorial/${imgs[i]}.webp" alt="Imagem ilustrativa da ideia" loading="lazy" /><span class="idea-number">0${i+1} ↗</span></div><div class="idea-copy"><div class="idea-brand-top">${safe(x.project)}</div><h3>${safe(x.title)}</h3><p>${safe(excerpt(x.description,148))}</p><div class="idea-brand">IDEIA PARA TESTAR ↗</div></div></article>`).join('');
  }
  function renderInsights(){const o=state.edition.opportunity||{};$('opportunityTitle').textContent=o.title||'Uma oportunidade nasce de observar melhor.';$('opportunityText').textContent=o.description||'Volte amanhã para os novos sinais e experimentos.';$('opportunityTag').textContent=o.tag||'IDEIA A TESTAR';$('signalText').textContent=state.edition.signal||'Em observação.';}
  function openArticle(id){const a=(state.edition.articles||[]).find(x=>x.id===id);if(!a)return;
    $('dialogContent').innerHTML=`<div class="dialog-content"><div class="dialog-cover">${imageTag(a,0)}</div><div class="article-topic">${badge(a)}</div><h2>${safe(a.title)}</h2><p class="dialog-lead">${safe(a.summary)}</p><div class="dialog-separator"></div><h4>POR QUE ISSO IMPORTA</h4><p>${safe(a.why||'Considere as implicações para sua estratégia.')}</p><h4>O QUE VOCÊ PODE FAZER</h4><p>${safe(a.action||'Leia a publicação original antes de aplicar.')}</p><h4>PROCEDÊNCIA DA INFORMAÇÃO</h4><p class="dialog-meta">${safe(a.source)} · ${safe(prettyDate(a.published_at))} · ${safe(a.verification||'Fonte identificada')} · ${safe(a.language||'')}</p><div class="dialog-actions"><a target="_blank" rel="noopener noreferrer" href="${safeUrl(a.url)}">Abrir fonte original ↗</a><button data-save="${safe(a.id)}">${state.saved.includes(a.id)?'★ Salvo':'☆ Salvar matéria'}</button><button data-copy="${safe(a.id)}">Copiar link</button></div></div>`;
    const dlg=$('articleDialog');if(!dlg.open && typeof dlg.showModal==='function')dlg.showModal();else if(!dlg.open)dlg.setAttribute('open','');}
  function toggleSave(id){const has=state.saved.includes(id);state.saved=has?state.saved.filter(x=>x!==id):[...state.saved,id];persist();render();if($('articleDialog').open)openArticle(id);toast(has?'Removido dos salvos':'Matéria salva neste dispositivo')}
  async function loadEdition(path, label){try{const response=await fetch(path+'?v='+Date.now(),{cache:'no-store'});if(!response.ok)throw Error('Edição não encontrada');const d=await response.json();if(!Array.isArray(d.articles))throw Error('Formato inválido');state.edition=d;state.current=label||'latest';state.filter='Todos';state.search='';state.visibleArticles=6;state.visibleVirals=6;$('searchInput').value='';document.querySelectorAll('.nav-tab').forEach(b=>b.classList.toggle('active',b.dataset.filter==='Todos'));render();return true}catch(e){if(label==='latest'){state.edition=window.BOOTSTRAP_EDITION||state.edition;state.current='latest';render();}toast('Não foi possível carregar essa edição. Confira a conexão.');return false}}
  async function loadArchiveIndex(){try{const response=await fetch('data/archive/index.json',{cache:'no-store'});if(!response.ok)throw Error();const data=await response.json();for(const entry of data.editions||[]){const opt=document.createElement('option');opt.value=entry.path;opt.textContent=entry.label;$('archiveSelect').appendChild(opt)}}catch{const opt=document.createElement('option');opt.value='data/archive/'+state.edition.edition_date+'.json';opt.textContent=prettyDate(state.edition.edition_date);$('archiveSelect').appendChild(opt)}}
  document.addEventListener('click',(ev)=>{const tab=ev.target.closest('[data-banner-index]');if(tab){selectBanner(Number(tab.dataset.bannerIndex));return}const b=ev.target.closest('[data-open],[data-save],[data-copy]');if(!b)return;const id=b.dataset.open||b.dataset.save||b.dataset.copy;if(b.dataset.open)openArticle(id);else if(b.dataset.save)toggleSave(id);else {const a=(state.edition.articles||[]).find(x=>x.id===id);if(a)navigator.clipboard?.writeText(a.url).then(()=>toast('Link da fonte copiado')).catch(()=>toast('Não foi possível copiar'))}});
  $('bannerPrev').addEventListener('click',()=>selectBanner(state.activeBanner-1));
  $('bannerNext').addEventListener('click',()=>selectBanner(state.activeBanner+1));
  $('bannerAutoplay').addEventListener('click',()=>{state.bannerPaused=!state.bannerPaused;syncBannerPlayButton()});
  $('dailyBanner').addEventListener('keydown',(ev)=>{if(ev.key==='ArrowLeft'){ev.preventDefault();selectBanner(state.activeBanner-1)}if(ev.key==='ArrowRight'){ev.preventDefault();selectBanner(state.activeBanner+1)}});
  let gestureX=null; $('dailyBanner').addEventListener('touchstart',(ev)=>{gestureX=ev.changedTouches[0].clientX},{passive:true});$('dailyBanner').addEventListener('touchend',(ev)=>{if(gestureX===null)return;const dx=ev.changedTouches[0].clientX-gestureX;if(Math.abs(dx)>55)selectBanner(state.activeBanner+(dx<0?1:-1));gestureX=null},{passive:true});
  if(!window.matchMedia('(prefers-reduced-motion: reduce)').matches){setInterval(()=>{if(!state.bannerPaused&&!document.hidden&&!$('dailyBanner').matches(':hover')&&!$('dailyBanner').contains(document.activeElement))selectBanner(state.activeBanner+1,false)},8500)}
  $('closeDialog').addEventListener('click',()=>$('articleDialog').close());$('articleDialog').addEventListener('click',(e)=>{if(e.target===$('articleDialog'))$('articleDialog').close()});
  function activateFilter(value, scroll=true) {
    state.filter=value;
    state.visibleArticles=6;
    document.querySelectorAll('.nav-tab').forEach(b=>b.classList.toggle('active',b.dataset.filter===value));
    renderNews();
    if(scroll) document.querySelector('#mais-noticias').scrollIntoView({behavior:'smooth',block:'start'});
  }
  document.querySelectorAll('.nav-tab').forEach(btn=>btn.addEventListener('click',()=>activateFilter(btn.dataset.filter)));
  document.querySelectorAll('[data-section-filter]').forEach(el=>el.addEventListener('click',(event)=>{
    event.preventDefault();activateFilter(el.dataset.sectionFilter);
  }));
  $('moreNews').addEventListener('click',()=>{state.visibleArticles+=6;renderNews()});
  $('moreVirals').addEventListener('click',()=>{state.visibleVirals+=6;renderVirals()});
  $('searchToggle').addEventListener('click',()=>{const hide=!$('searchPanel').hidden;$('searchPanel').hidden=hide;$('searchToggle').setAttribute('aria-expanded',String(!hide));if(!hide)$('searchInput').focus()});
  $('searchClose').addEventListener('click',()=>{$('searchPanel').hidden=true;$('searchInput').value='';state.search='';renderNews()});$('searchInput').addEventListener('input',(e)=>{state.search=e.target.value;state.visibleArticles=6;renderNews()});
  $('clearFilters').addEventListener('click',()=>{state.filter='Todos';state.search='';state.visibleArticles=6;state.visibleVirals=6;$('searchInput').value='';document.querySelectorAll('.nav-tab').forEach(b=>b.classList.toggle('active',b.dataset.filter==='Todos'));renderNews()});
  $('themeBtn').addEventListener('click',()=>{document.body.classList.toggle('dark');$('themeGlyph').textContent=document.body.classList.contains('dark')?'☼':'◐'});
  $('refreshBtn').addEventListener('click',async()=>{const ok=await loadEdition('data/latest.json','latest');if(ok)toast('Edição mais recente carregada')});
  $('viewArchive').addEventListener('click',async()=>{const path=$('archiveSelect').value;const ok=await loadEdition(path==='latest'?'data/latest.json':path,path==='latest'?'latest':'archive');if(ok){window.scrollTo({top:0,behavior:'smooth'});toast('Edição aberta')}});
  render();loadArchiveIndex();
  // Ao abrir o arquivo HTML sem servidor, o bootstrap embutido garante uma edição utilizável.
  if(location.protocol!=='file:')loadEdition('data/latest.json','latest');
})();
