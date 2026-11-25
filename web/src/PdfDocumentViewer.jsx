import React, { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, LoaderCircle } from 'lucide-react';

// Assets are bundled by Vite and loaded from this application, never a CDN.
const pdfAssets = import.meta.glob([
  '../node_modules/pdfjs-dist/cmaps/*.bcmap',
  '../node_modules/pdfjs-dist/standard_fonts/*.{pfb,ttf}',
  '../node_modules/pdfjs-dist/wasm/*.wasm',
], { query: '?url', import: 'default' });

class LocalPdfAssets {
  async fetch({ kind, filename }) {
    const directory = { cMapUrl: 'cmaps', standardFontDataUrl: 'standard_fonts', wasmUrl: 'wasm' }[kind];
    const load = pdfAssets[`../node_modules/pdfjs-dist/${directory}/${filename}`];
    if (!load) throw new Error('PDF resource unavailable');
    const response = await fetch(await load());
    if (!response.ok) throw new Error('PDF resource could not be loaded');
    return new Uint8Array(await response.arrayBuffer());
  }
}

export default function PdfDocumentViewer({ url, zoom, onStatusChange }) {
  const [pdf, setPdf] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [width, setWidth] = useState(0);
  const [rendering, setRendering] = useState(false);
  const [failed, setFailed] = useState(false);
  const scrollRef = useRef(null);
  const surfaceRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    let loadingTask;
    setPdf(null);
    setFailed(false);
    setPageNumber(1);
    onStatusChange('loading');
    async function loadDocument() {
      try {
        const [pdfjs, { default: workerUrl }] = await Promise.all([
          import('pdfjs-dist/build/pdf.mjs'),
          import('pdfjs-dist/build/pdf.worker.min.mjs?url'),
        ]);
        if (cancelled) return;
        pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;
        loadingTask = pdfjs.getDocument({
          url, useWorkerFetch: false, BinaryDataFactory: LocalPdfAssets,
          useSystemFonts: true, stopAtErrors: true,
        });
        const document = await loadingTask.promise;
        if (!cancelled) setPdf(document);
      } catch {
        if (!cancelled) { setFailed(true); onStatusChange('fallback'); }
      }
    }
    void loadDocument();
    return () => {
      cancelled = true;
      if (loadingTask) void loadingTask.destroy().catch(() => {});
    };
  }, [url, onStatusChange]);

  useEffect(() => {
    const element = scrollRef.current;
    if (!element) return undefined;
    const measure = () => setWidth(Math.floor(element.clientWidth));
    measure();
    if (typeof ResizeObserver === 'undefined') {
      window.addEventListener('resize', measure);
      return () => window.removeEventListener('resize', measure);
    }
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    return () => observer.disconnect();
  }, [failed]);

  useEffect(() => {
    if (!pdf || width <= 0 || failed) return undefined;
    let cancelled = false;
    let renderTask;
    setRendering(true);
    async function renderPage() {
      try {
        const page = await pdf.getPage(pageNumber);
        if (cancelled) return;
        const base = page.getViewport({ scale: 1 });
        const fitScale = Math.max(1, width - 32) / base.width;
        const viewport = page.getViewport({ scale: fitScale * ((zoom ?? 100) / 100) });
        // Keep a single page canvas in memory; bound its backing resolution.
        const density = Math.min(window.devicePixelRatio || 1, 2,
          Math.sqrt(16000000 / (viewport.width * viewport.height)),
          8192 / viewport.width, 8192 / viewport.height);
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.floor(viewport.width * density));
        canvas.height = Math.max(1, Math.floor(viewport.height * density));
        canvas.style.width = `${viewport.width}px`;
        canvas.style.height = `${viewport.height}px`;
        canvas.setAttribute('role', 'img');
        canvas.setAttribute('aria-label', `Trang ${pageNumber} trên ${pdf.numPages} của chứng từ gốc`);
        renderTask = page.render({ canvas, viewport, transform: [density, 0, 0, density, 0, 0] });
        await renderTask.promise;
        if (cancelled) return;
        const surface = surfaceRef.current;
        if (!surface) return;
        surface.replaceChildren(canvas);
        setRendering(false);
        onStatusChange('ready');
      } catch (error) {
        if (!cancelled && error?.name !== 'RenderingCancelledException') {
          setRendering(false);
          setFailed(true);
          onStatusChange('fallback');
        }
      }
    }
    void renderPage();
    return () => { cancelled = true; renderTask?.cancel(); };
  }, [pdf, pageNumber, zoom, width, failed, onStatusChange]);

  function goToPage(value) {
    const nextPage = Number(value);
    if (!pdf || !Number.isInteger(nextPage) || nextPage < 1 || nextPage > pdf.numPages) return;
    setPageNumber(nextPage);
    scrollRef.current?.scrollTo({ top: 0, left: 0 });
  }

  if (failed) return <div className="invoice-pdf-fallback">
    <p role="status">Đã chuyển sang trình xem PDF của trình duyệt. Dùng các nút trên tài liệu để thu phóng và chuyển trang.</p>
    <iframe title="Chứng từ PDF — trình xem dự phòng" src={`${url}#toolbar=1&navpanes=0&view=FitH`}/>
  </div>;

  return <div className="invoice-pdf-viewer">
    <div className="invoice-pdf-scroll" ref={scrollRef} tabIndex={0} role="region" aria-label="Nội dung PDF có thể cuộn" aria-busy={!pdf || rendering}>
      {(!pdf || rendering) && <div className="invoice-pdf-loading" role="status"><LoaderCircle size={16} className="spin"/>Đang hiển thị trang…</div>}
      <div className="invoice-pdf-surface" ref={surfaceRef}/>
    </div>
    <div className="invoice-pdf-pagination" aria-label="Chuyển trang PDF">
      <button type="button" className="iconbtn" disabled={!pdf || pageNumber <= 1} aria-label="Trang PDF trước" onClick={() => goToPage(pageNumber - 1)}><ChevronLeft size={17}/></button>
      <label>Trang<input aria-label="Số trang PDF" type="number" min={1} max={pdf?.numPages || 1} disabled={!pdf} value={pageNumber} onChange={event => goToPage(event.target.value)}/></label>
      <span>/ {pdf?.numPages ?? '…'}</span>
      <button type="button" className="iconbtn" disabled={!pdf || pageNumber >= pdf.numPages} aria-label="Trang PDF tiếp theo" onClick={() => goToPage(pageNumber + 1)}><ChevronRight size={17}/></button>
    </div>
  </div>;
}
