import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';

const root = new URL('../static/', import.meta.url);
const [support, login, knowledgeBase, supportJs, adminJs, styles] = await Promise.all([
  readFile(new URL('index.html', root), 'utf8'), readFile(new URL('admin-login.html', root), 'utf8'),
  readFile(new URL('knowledge-base.html', root), 'utf8'), readFile(new URL('support.js', root), 'utf8'),
  readFile(new URL('admin.js', root), 'utf8'), readFile(new URL('styles.css', root), 'utf8'),
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
  assert.match(styles, /--accent:#b8ff48/); assert.match(styles, /@media/);
});
