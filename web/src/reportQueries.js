export function reportQueries(filters, {page, pageSize, sortBy, sortOrder}) {
  const applied = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
  const sorted = new URLSearchParams(applied);
  sorted.set('sort_by', sortBy);
  sorted.set('sort_order', sortOrder);

  const preview = new URLSearchParams(sorted);
  preview.set('limit', pageSize);
  preview.set('offset', page * pageSize);

  return {
    summary: '/reports/summary' + (applied.size ? '?' + applied : ''),
    preview: '/reports/invoices?' + preview,
    export: '/reports/export?' + sorted,
  };
}
