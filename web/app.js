const $=id=>document.getElementById(id);
const names={hormozi:'Alex Hormozi',naval:'Naval Ravikant',kallaway:'Kallaway'};
const element=(tag,text)=>{const el=document.createElement(tag);if(text)el.textContent=text;return el;};
$('query').onsubmit=async event=>{
 event.preventDefault();$('ask').disabled=true;$('status').textContent='Finding evidence'+($('retrieval').checked?'…':' and composing grounded answers. Local inference may take a minute per advisor…');$('results').replaceChildren();
 try{
  const response=await fetch('/api/query',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:$('question').value,advisor:$('advisor').value,retrieval_only:$('retrieval').checked}),signal:AbortSignal.timeout(600000)});
  const data=await response.json();if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'Please check your question.');
  if(data.council_synthesis){
   const s=data.council_synthesis,card=element('article');card.className='synthesis';card.append(element('h2','Council synthesis'));
   if(s.advisors_abstained.length)card.append(element('p',`No answer from: ${s.advisors_abstained.map(a=>names[a]||a).join(', ')}.`));
   if(s.shared_topics.length){card.append(element('h3','Shared topics'));for(const pair of s.shared_topics){card.append(element('p',`${names[pair.advisors[0]]} & ${names[pair.advisors[1]]} both touch on: ${pair.shared_terms.join(', ')}`));card.append(element('p',`${names[pair.advisors[0]]}: "${pair.claims[0].text}" — ${names[pair.advisors[1]]}: "${pair.claims[1].text}"`));}}
   if(s.distinct_perspectives.length){card.append(element('h3','Distinct perspectives'));for(const pair of s.distinct_perspectives)card.append(element('p',`${names[pair.advisors[0]]}: "${pair.claims[0].text}" — ${names[pair.advisors[1]]}: "${pair.claims[1].text}"`));}
   card.append(element('small',s.note));$('results').append(card);
  }
  for(const result of data.results){
   const card=element('article');card.append(element('h2',names[result.advisor]));
   if(result.error)card.append(element('p',result.error));
   if(result.answer?.status==='insufficient_evidence')card.append(element('p','The available sources do not support an answer to this question.'));
   for(const claim of result.answer?.claims||[]){const p=element('p',claim.text+' ');for(const cid of claim.citations){const source=result.evidence.find(x=>x.chunk_id===cid);const a=element('a','[source]');a.href=source.url;a.target='_blank';a.rel='noopener noreferrer';p.append(a);}card.append(p);}
   const details=element('details');if(!result.answer)details.open=true;details.append(element('summary',`${result.evidence.length} retrieved source excerpts`));
   for(const source of result.evidence){const block=element('div');block.className='source';const link=element('a',source.title);link.href=source.url;link.target='_blank';link.rel='noopener noreferrer';block.append(link,element('p',source.text),element('small',source.attribution));details.append(block);}card.append(details);$('results').append(card);
  }
  $('status').textContent=`${(data.duration_ms/1000).toFixed(1)}s · ${data.comparison_note}`;
 }catch(e){$('status').textContent=e.message;}finally{$('ask').disabled=false;}
};
