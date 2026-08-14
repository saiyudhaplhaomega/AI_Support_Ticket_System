import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
const html = await readFile(new URL('../static/index.html', import.meta.url), 'utf8');
test('demo browser presents every safe mock-result field', () => { for (const label of ['Mock classification JSON','Top-3 RAG sources and fallback decision','Routing decision','Manual-review status','Processing log','Internal-draft-only reply']) assert.match(html, new RegExp(label)); assert.match(html, /renderDemo\(data\.demo\)/); assert.match(html, /internal draft only/i); });
test('browser-side validation keeps PDF errors readable', () => { assert.match(html, /Attachment must be a PDF\./); assert.match(html, /Attachment must be 10 MB or smaller\./); assert.match(html, /Unable to reach the local demo server/); });
