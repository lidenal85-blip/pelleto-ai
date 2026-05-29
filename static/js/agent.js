// agent.js — M2 AgentWidget
(function(){
  'use strict';

  var SESSION_KEY = 'pelleto_session';
  var HISTORY_KEY = 'pelleto_history';
  var MAX_HISTORY = 10;
  var ROOT_PATH   = (document.body.dataset.rootPath || '');
  var ORDER_URL   = ROOT_PATH + '/order';

  // Генерация session_id
  function getSession(){
    var s = sessionStorage.getItem(SESSION_KEY);
    if(!s){ s = 'sess-'+Math.random().toString(36).slice(2)+Date.now(); sessionStorage.setItem(SESSION_KEY,s); }
    return s;
  }

  function getHistory(){
    try{ return JSON.parse(sessionStorage.getItem(HISTORY_KEY)||'[]'); }catch(e){ return []; }
  }
  function saveHistory(h){
    sessionStorage.setItem(HISTORY_KEY, JSON.stringify(h.slice(-MAX_HISTORY)));
  }

  var toggle   = document.getElementById('agent-toggle');
  var chat     = document.getElementById('agent-chat');
  var closeBtn = document.getElementById('agent-close');
  var messages = document.getElementById('agent-messages');
  var input    = document.getElementById('agent-input');
  var sendBtn  = document.getElementById('agent-send');

  if(!toggle) return;

  toggle.addEventListener('click', function(){
    chat.classList.toggle('hidden');
    if(!chat.classList.contains('hidden')) input.focus();
  });
  closeBtn.addEventListener('click', function(){ chat.classList.add('hidden'); });

  function appendMsg(text, role){
    var div = document.createElement('div');
    div.className = 'agent-msg agent-msg--' + (role==='user'?'user':'bot');
    // XSS protection: textContent only
    div.textContent = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
    return div;
  }

  function appendCTA(text, url){
    var div = document.createElement('div');
    div.className = 'agent-cta';
    var a = document.createElement('a');
    a.href = url;
    a.textContent = text;
    div.appendChild(a);
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  }

  function send(){
    var q = input.value.trim();
    if(!q) return;
    if(q.length > 500){ alert('Вопрос слишком длинный. Максимум 500 символов.'); return; }

    appendMsg(q, 'user');
    input.value = '';
    sendBtn.disabled = true;

    var typing = appendMsg('Печатает...', 'bot');
    typing.className += ' agent-msg--typing';

    var history = getHistory();
    var requestId = 'r-'+Math.random().toString(36).slice(2);

    fetch(ROOT_PATH + '/api/agent/chat', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Request-ID': requestId
      },
      body: JSON.stringify({
        question: q,
        session_id: getSession(),
        history: history
      })
    })
    .then(function(r){ return r.json(); })
    .then(function(data){
      messages.removeChild(typing);
      var answer = data.answer || data.fallback_message || 'Ошибка связи. Позвоните нам.';
      appendMsg(answer, 'bot');
      if(data.cta && data.cta.show){
        appendCTA(data.cta.text||'Оформить заказ', data.cta.url||ORDER_URL);
      }
      // Сохраняем историю
      history.push({role:'user',content:q});
      history.push({role:'assistant',content:answer});
      saveHistory(history);
    })
    .catch(function(){
      messages.removeChild(typing);
      appendMsg('Нет связи с сервером. Попробуйте позже.', 'bot');
    })
    .finally(function(){ sendBtn.disabled = false; input.focus(); });
  }

  sendBtn.addEventListener('click', send);
  input.addEventListener('keydown', function(e){ if(e.key==='Enter') send(); });
})();