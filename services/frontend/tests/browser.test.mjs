import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../static/', import.meta.url);
const [support, login, knowledgeBase, supportJs, adminJs, styles, customStyles, chat, chatJs, adminAssistant, adminAssistantJs] = await Promise.all([
  readFile(new URL('index.html', root), 'utf8'), readFile(new URL('admin-login.html', root), 'utf8'),
  readFile(new URL('knowledge-base.html', root), 'utf8'), readFile(new URL('support.js', root), 'utf8'),
  readFile(new URL('admin.js', root), 'utf8'), readFile(new URL('styles.css', root), 'utf8'),
  readFile(new URL('custom.css', root), 'utf8'), readFile(new URL('chat.html', root), 'utf8'),
  readFile(new URL('chat.js', root), 'utf8'), readFile(new URL('admin-assistant.html', root), 'utf8'),
  readFile(new URL('admin-assistant.js', root), 'utf8'),
]);

test('public support and administrator controls are separate pages', () => {
  assert.match(support, /Support ticket/); assert.doesNotMatch(support, /Administrator sign in/);
  assert.match(login, /Administrator sign in/); assert.match(login, /Continue with Google/);
  assert.match(login, /\/api\/auth\/google\/login/); assert.match(knowledgeBase, /Knowledge update/);
  assert.match(knowledgeBase, /Sign out/);
});

test('client UI preserves readable attachment and administrator feedback', () => {
  assert.match(supportJs, /Attachment must be a PDF/); assert.match(supportJs, /10 MB or smaller/);
  assert.match(adminJs, /api\/knowledge-base\/session/); assert.match(adminJs, /Indexing document/);
  assert.match(styles, /--acid:#d8ff54/); assert.match(styles, /@media/);
});

test('public chat expands from an accessible side launcher and sends with Enter', () => {
  assert.match(support, /id="chat-widget"[^>]*hidden/);
  assert.match(support, /id="chat-toggle"[^>]*aria-controls="chat-widget"/);
  assert.match(support, /id="chat-close"/);
  assert.match(support, /id="chat-thread" aria-live="polite"/);
  assert.match(support, /id="chat-message"/); assert.match(support, /Press Enter to send/);
  assert.match(chatJs, /event\.key==='Enter'&&!event\.shiftKey/);
  assert.match(chatJs, /event\.preventDefault\(\);send\(\)/);
  assert.match(chatJs, /function setOpen\(open\)/); assert.match(chatJs, /else toggle\.focus\(\)/);
  assert.match(chatJs, /closeButton\.addEventListener/); assert.match(chatJs, /event\.key==='Escape'/);
  assert.match(chatJs, /^\(\(\)=>\{/);
  assert.match(customStyles, /\.chat-fab/); assert.match(customStyles, /\.chat-widget/);
});

test('administrator assistant is a separate private chat surface with keyboard send', () => {
  assert.match(adminAssistant, /id="admin-chat-thread" aria-live="polite"/);
  assert.match(adminAssistant, /id="admin-chat-message"/);
  assert.match(adminAssistant, /Private guidance only/);
  assert.match(adminAssistantJs, /\/api\/admin\/assistant/);
  assert.match(adminAssistantJs, /event\.key==='Enter'&&!event\.shiftKey/);
});
