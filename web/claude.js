/* Claude DOM adapter: selected conversation only; no cookies or private APIs. */
(() => {
  const state = window.__meetVoiceClaudeState ||= {current: null};
  const visible = el => !!el && el.getClientRects().length > 0 && getComputedStyle(el).visibility !== 'hidden';
  const label = el => [el.getAttribute('aria-label'), el.getAttribute('title'), el.textContent].filter(Boolean).join(' ');
  const buttons = () => [...document.querySelectorAll('button,[role="button"]')].filter(visible);
  const editor = () => [...document.querySelectorAll('#prompt-textarea[contenteditable="true"],textarea#prompt-textarea,[contenteditable="true"][role="textbox"],[contenteditable="true"].tiptap,[contenteditable="true"].ProseMirror')].find(visible);
  const responses = () => [...document.querySelectorAll('[data-is-streaming],.font-claude-response,[data-testid="assistant-message"]')].filter(n => !n.parentElement?.closest('[data-is-streaming],.font-claude-response,[data-testid="assistant-message"]'));
  const stop = () => document.querySelector('[data-testid="stop-button"]') || buttons().find(b => /^stop\b|зупинити|остановить/i.test(label(b)));
  function responseText(node) {
    const copy = (node.querySelector('[data-perf-reply-text]') || [...node.querySelectorAll('[data-markdown-text-style="assistant-message"]')].at(-1) || node.querySelector('.markdown') || node).cloneNode(true);
    copy.querySelectorAll('button,script,style,[aria-hidden="true"],.turn-action-controls,[class~="sr-only"],[class~="group/user-message"],[data-content-search-unit-key$=":user"],[data-claude-search-unit-key$=":user"]').forEach(n => n.remove());
    return copy.textContent.trim();
  }
  const changed = () => new Promise(resolve => {
    let timer;
    const done = () => {observer.disconnect(); clearTimeout(timer); resolve();};
    const observer = new MutationObserver(done);
    observer.observe(document.documentElement, {subtree:true, childList:true, attributes:true, characterData:true});
    timer = setTimeout(done, 500);
  });
  function check(job) {
    if (state.current !== job || job.cancelled) throw new Error('Запит скасовано.');
    if (location.origin + location.pathname !== job.url) throw new Error('Claude перейшов в іншу розмову.');
  }
  function phase(job, message) {browser.runtime.sendMessage({action:'progress', id:job.id, message}).catch(() => {});}
  async function until(job, fn, timeout, message) {
    const deadline = Date.now() + timeout;
    while (true) {check(job); const value = fn(); if (value) return value;
      if (Date.now() >= deadline) throw new Error(message); await changed();}
  }
  function fileInput() {return [...document.querySelectorAll('input[type="file"]')].find(n => !n.accept || /image|\.png|\*/i.test(n.accept));}
  async function solve(data) {
    if (state.current) throw new Error('Попередній запит ще виконується.');
    const job = {...data, cancelled:false}; state.current = job;
    try {
      check(job);
      if (stop()) throw new Error('Claude уже генерує відповідь.');
      const inputEditor = editor();
      if (!inputEditor) throw new Error('Не знайдено поле повідомлення Claude.');
      if ((inputEditor.value || inputEditor.innerText || '').trim()) throw new Error('У Claude є чернетка. Надішліть або приберіть її.');
      const turnKey = node => node.getAttribute('data-turn-key') || node.closest('[data-message-id]')?.getAttribute('data-message-id') || node;
      const baseline = new Set(responses().map(turnKey));
      if (!data.text?.trim()) throw new Error('Немає розпізнаного тексту. Аудіо для Claude потрібно обробити локальним Whisper.');
      if (!Array.isArray(data.files) || data.files.length > 1 || data.files.some(f => f.mime !== 'image/png'))
        throw new Error('Claude отримує текст і необов’язковий PNG, а не WAV.');
      if (data.files.length) {
        if (!fileInput()) {
          const add = document.querySelector('#composer-plus-btn') || buttons().find(b => /attach|upload|add photos|add files|додати файли|добавить файлы/i.test(label(b)));
          if (!add) throw new Error('Не знайдено кнопку додавання файлів Claude.');
          add.click();
        }
        const upload = await until(job, fileInput, 15000, 'Claude не показав поле завантаження файлу.');
        const item = data.files[0];
        const bytes = Uint8Array.from(atob(item.data), c => c.charCodeAt(0));
        const transfer = new DataTransfer(); transfer.items.add(new File([bytes], item.name, {type:item.mime}));
        const form = inputEditor.closest('form') || inputEditor.parentElement?.parentElement || document.body;
        const oldImages = new Set([...form.querySelectorAll('img')].map(n => n.src));
        upload.files = transfer.files; upload.dispatchEvent(new Event('change', {bubbles:true}));
        phase(job, 'Скриншот передано Claude; очікую вкладення.');
        await until(job, () => [...form.querySelectorAll('img')].some(n => !oldImages.has(n.src) && n.complete && n.naturalWidth > 0) ||
          [...form.querySelectorAll('[aria-label],[title]')].some(n => label(n).includes(item.name)) || form.textContent.includes(item.name),
          30000, 'Claude не підтвердив прикріплення скриншота. Запит не надіслано.');
      }
      check(job);
      // Only the transcript is inserted; the user provides chat instructions.
      const targetEditor = editor();
      if (!targetEditor || (targetEditor.value || targetEditor.innerText || '').trim()) throw new Error('Поле Claude змінилося або містить чернетку.');
      targetEditor.focus();
      if (targetEditor.tagName === 'TEXTAREA') {
        const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
        setter.call(targetEditor, data.text);
        targetEditor.dispatchEvent(new Event('input', {bubbles:true}));
      } else {
        // Background Firefox tabs may have no editable selection after focus().
        const selection = document.getSelection();
        const range = document.createRange();
        range.selectNodeContents(targetEditor); range.collapse(false);
        selection.removeAllRanges(); selection.addRange(range);
        document.execCommand('insertText', false, data.text);
        if (!(targetEditor.innerText || '').trim()) {
          // ProseMirror observes DOM edits and reconciles them into its document.
          // Use plain text nodes only, never HTML from the transcript.
          const paragraph = document.createElement('p');
          paragraph.textContent = data.text;
          targetEditor.replaceChildren(paragraph);
          targetEditor.dispatchEvent(new InputEvent('input', {bubbles:true, composed:true, inputType:'insertText', data:data.text}));
        }
      }
      await until(job, () => (editor()?.value || editor()?.innerText || '').replace(/\s+/g,' ').trim() === data.text.replace(/\s+/g,' ').trim(), 5000, 'Claude не підтвердив текст у полі повідомлення.');
      const send = await until(job, () => {
        const b = document.querySelector('[data-testid="send-button"]') || buttons().find(n => /^(send\b|надіслати|отправить)/i.test(label(n).trim()));
        return b && !b.disabled && b.getAttribute('aria-disabled') !== 'true' ? b : null;
      }, 30000, 'Кнопка надсилання Claude недоступна. Перевірте вкладення або ліміти.');
      check(job); send.click(); phase(job, 'Текст надіслано. Очікую Claude.');
      const text = await until(job, () => {
        const last = responses().filter(n => !baseline.has(turnKey(n))).at(-1);
        if (!last || stop()) return null;
        let article = last;
        let complete = false;
        for (let i = 0; article && i < 4; i++, article = article.parentElement) {
          if ([...article.querySelectorAll('button')].some(b => /copy|копіювати|скопировать/i.test(label(b)))) {complete = true; break;}
        }
        if (last.getAttribute('data-is-streaming') === 'true') return null;
        const value = responseText(last);
        return complete && value ? value : null;
      }, 300000, 'Claude не завершив відповідь за 5 хвилин. Перевірте чат.');
      return {text};
    } finally {if (state.current === job) state.current = null;}
  }
  window.__meetVoiceClaudeHandler = data => {
    if (data.type === 'inspect') return Promise.resolve({provider:'claude',  visibility:document.visibilityState, editor:!!editor(), editorDetails:editor()?{tag:editor().tagName,role:editor().getAttribute('role'),classes:editor().className,editable:editor().getAttribute('contenteditable'),html:editor().innerHTML.slice(0,500)}:null, fileInputs:document.querySelectorAll('input[type="file"]').length, responses:responses().length, lastResponse:responses().length ? responseText(responses().at(-1)).slice(0,500) : '', buttons:buttons().map(label).slice(-30), url:location.origin+location.pathname});
    if (data.type === 'cancel' && state.current?.id === data.id) {state.current.cancelled=true; const b=stop(); if(b) b.click(); return Promise.resolve({ok:true});}
    if (data.type === 'solve') return solve(data).catch(e => ({error:String(e.message).slice(0,400)}));
  };
  if (!window.__meetVoiceClaudeListener) {
    window.__meetVoiceClaudeListener = data => window.__meetVoiceClaudeHandler(data);
    browser.runtime.onMessage.addListener(window.__meetVoiceClaudeListener);
  }
})();
