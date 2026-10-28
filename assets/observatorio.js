(() => {
  // Observatório separado da edição jornalística. Sem casos fabricados ou métricas inventadas.
  const fields=['creators','collaborations','brands','local','run'];
  const esc = (s) => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function draw(data) {
    for(const field of fields) {
      const el=document.getElementById('watch-list-'+field);
      if(!el)continue;
      const items=Array.isArray(data[field])?data[field].filter(x=>x&&typeof x.title==='string'&&/^https:\/\//.test(x.source_url||'')).slice(0,20):[];
      if(!items.length)continue;
      el.innerHTML=items.map((x,i)=>{
        let verification=['confirmado','indício','hipótese'].includes(x.verification)?x.verification:'em avaliação';
        return `<div class="watch-list-item" ${i>=4?'hidden':''}><strong>${esc(x.title)}</strong><span>${esc(x.region||'')}${x.region?' · ':''}${esc(verification)}${x.date?' · '+esc(x.date):''}</span><span>${esc(x.summary||'')}</span><a href="${esc(x.source_url)}" target="_blank" rel="noopener noreferrer">Ver fonte ↗</a></div>`
      }).join('');
      if(items.length>4) {
        const btn=document.createElement('button');btn.type='button';btn.className='watch-explore';btn.textContent=`Mostrar mais ${Math.min(6,items.length-4)} de ${items.length} casos ↓`;
        let visible=4; btn.addEventListener('click',()=>{visible=Math.min(visible+6,items.length);Array.from(el.querySelectorAll('.watch-list-item')).forEach((node,i)=>{node.hidden=i>=visible});btn.hidden=visible>=items.length;if(!btn.hidden)btn.textContent=`Mostrar mais ${Math.min(6,items.length-visible)} de ${items.length} casos ↓`});el.after(btn);
      }
      const status=el.closest('.watch-card')?.querySelector('.watch-status');
      if(status && el.innerHTML)status.textContent=`${items.length} CASOS`;
    }
  }
  if(location.protocol!=='file:') fetch('data/watchlist.json',{cache:'no-store'}).then(r=>r.ok?r.json():null).then(d=>{if(d)draw(d)}).catch(()=>{});
})();
