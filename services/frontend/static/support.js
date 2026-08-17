const form = document.querySelector('#ticket');
const result = document.querySelector('#result');
const notice = document.querySelector('#notice');
const demoResult = document.querySelector('#demo-result');
const demoNote = document.querySelector('#demo-note');
const fields = document.querySelector('#demo-fields');
const pdfTypes = new Set(['application/pdf', 'application/x-pdf']);

fetch('/api/mode').then((response) => response.json()).then(({ mode }) => {
  notice.textContent = mode === 'test'
    ? 'Safe demonstration mode. No ticket is sent to external services.'
    : 'Live mode. Your request is submitted to the NOAVIA support workflow.';
}).catch(() => { notice.textContent = 'Service status could not be checked.'; });

function showError(message) {
  result.className = 'form-result error';
  result.textContent = message;
  demoResult.hidden = true;
}

function addField(label, value) {
  const term = document.createElement('dt');
  term.textContent = label;
  const description = document.createElement('dd');
  const output = document.createElement('pre');
  output.textContent = JSON.stringify(value, null, 2);
  description.append(output);
  fields.append(term, description);
}

function renderResult(data) {
  fields.replaceChildren();
  demoNote.textContent = data.demo
    ? 'This is an internal demonstration result. It was not sent to a customer.'
    : 'This is the workflow acknowledgement. Customer replies are never sent automatically.';
  if (data.demo) {
    addField('Classification', data.demo.classification);
    addField('Knowledge sources', data.demo.rag);
    addField('Routing', data.demo.routing);
    addField('Review status', data.demo.manual_review);
    addField('Processing log', data.demo.processing_log);
    addField('Internal draft', data.demo.internal_draft_reply);
  } else {
    addField('Workflow acknowledgement', data.webhook_response);
  }
  demoResult.hidden = false;
}

function asBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error('The attachment could not be read.'));
    reader.onload = () => resolve(String(reader.result).split(',')[1]);
    reader.readAsDataURL(file);
  });
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const attachment = form.attachment.files[0];
  if (attachment && !pdfTypes.has(attachment.type)) return showError('Attachment must be a PDF.');
  if (attachment && attachment.size > 10 * 1024 * 1024) return showError('Attachment must be 10 MB or smaller.');
  const payload = Object.fromEntries(new FormData(form));
  if (attachment) {
    payload.attachment_name = attachment.name;
    payload.attachment_type = attachment.type;
    try { payload.attachment_base64 = await asBase64(attachment); } catch (error) { return showError(error.message); }
  }
  result.className = 'form-result';
  result.textContent = 'Submitting request…';
  demoResult.hidden = true;
  try {
    const response = await fetch('/api/tickets', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(payload) });
    const data = await response.json();
    if (!response.ok || !data.ok) return showError(data.detail || data.message || 'Unable to submit the request.');
    result.textContent = `${data.message} Ticket: ${data.ticket_id}.`;
    renderResult(data);
    form.reset();
  } catch (_) { showError('Unable to reach the support service. Please try again.'); }
});
