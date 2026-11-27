
const collections = new Set([
  '/invoices', '/profile/invoices', '/dashboard/summary',
  '/reports/suppliers', '/reports/summary',
  '/reports/invoices', '/reports/export',
]);

export function invoiceReadPath(path, method = 'GET') {
  if (method.toUpperCase() !== 'GET') return path;
  const index = path.indexOf('?');
  const pathname = index < 0 ? path : path.slice(0, index);
  if (!collections.has(pathname)) return path;
  const query = new URLSearchParams(
    index < 0 ? '' : path.slice(index + 1)
  );
  query.delete('exclude_drafts');
  return `${pathname}?${query}`;
}
