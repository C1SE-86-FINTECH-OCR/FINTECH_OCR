import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeSanitize from 'rehype-sanitize';

export default function ChatMarkdown({children}) {
  return React.createElement(
    ReactMarkdown,
    {
      remarkPlugins: [remarkGfm, remarkBreaks, remarkMath],
      rehypePlugins: [rehypeSanitize, rehypeKatex],
    },
    String(children ?? ''),
  );
}
