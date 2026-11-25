import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
import ChatMarkdown from '../src/ChatMarkdown.js';

function render(markdown) {
  return renderToStaticMarkup(React.createElement(ChatMarkdown, null, markdown));
}

test('chat markdown renders emphasis, lists, tables, and line breaks', () => {
  const html = render('**Tổng hợp**\nDòng tiếp theo\n\n- Một\n- Hai\n\n| Cột | Giá trị |\n| --- | ---: |\n| Tổng | 1.000 ₫ |');
  assert.match(html, /<strong>Tổng hợp<\/strong>/);
  assert.match(html, /<br\s*\/>/);
  assert.match(html, /<ul>/);
  assert.match(html, /<table>/);
  assert.match(html, /1\.000 ₫/);
});

test('chat markdown does not execute raw HTML or javascript links', () => {
  const html = render('<script>alert(1)</script>\n\n<a href="javascript:alert(2)">bấm vào đây</a>');
  assert.doesNotMatch(html, /<script\b/i);
  assert.doesNotMatch(html, /href="javascript:/i);
});

test('chat markdown renders math formulas with KaTeX', () => {
  const html = render('$$A = P \\times \\left(1 + \\frac{r}{n}\\right)^{nt}$$\n\n- $A$: tổng số tiền sau $t$ năm.');
  assert.match(html, /class="katex"/);
});
