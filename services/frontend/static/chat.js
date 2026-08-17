const form = document.querySelector('#chat');
const result = document.querySelector('#chat-result');
const answer = document.querySelector('#chat-answer');
form.addEventListener('submit', async (event) => {
  event.preventDefault(); result.textContent = 'Searching approved information…'; answer.hidden = true;
  try { const response = await fetch('/api/chat', {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({message: form.message.value})}); const data = await response.json(); if (!response.ok || !data.ok) throw new Error(data.detail || 'Unable to answer that question.'); document.querySelector('#chat-text').textContent = data.answer; const sources = document.querySelector('#chat-sources'); sources.replaceChildren(...(data.sources || []).map(source => { const item=document.createElement('li'); item.textContent=typeof source==='string'?source:(source.title || source.source || 'Knowledge source'); return item; })); answer.hidden=false; result.textContent=''; } catch (error) { result.textContent=error.message; result.className='form-result error'; }
});
