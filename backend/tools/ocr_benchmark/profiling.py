"""Scoped, serial OFFLINE instrumentation; never installed in the API.

Inclusive/exclusive spans avoid summing nested OCR twice. No document text,
pixels, arguments or ground truth enter timing records. Hooks restore on error.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
from threading import RLock
from time import perf_counter

_active = ContextVar('offline_ocr_profile', default=None)
_lock = RLock()


class Profile:
    def __init__(self):
        self.events = []
        self.stack = []

    @contextmanager
    def span(self, name):
        node = {'stage': name, 'children_s': 0., 'depth': len(self.stack)}
        self.stack.append(node)
        start = perf_counter()
        try:
            yield
        except Exception as exc:
            node['error'] = type(exc).__name__
            raise
        finally:
            elapsed = perf_counter() - start
            self.stack.pop()
            if self.stack:
                self.stack[-1]['children_s'] += elapsed
            node.update(inclusive_s=elapsed, exclusive_s=max(0., elapsed-node.pop('children_s')))
            self.events.append(node)

    def report(self):
        totals = {}
        for e in self.events:
            t = totals.setdefault(e['stage'], {'calls': 0, 'inclusive_s': 0., 'exclusive_s': 0.})
            t['calls'] += 1
            for k in ('inclusive_s', 'exclusive_s'):
                t[k] += e[k]
        return {'method': 'perf_counter wall time; nested spans; serial offline hooks',
                'stages': totals, 'events': self.events,
                'ocr_calls': sum(e['stage'].startswith('engine.') for e in self.events)}


@contextmanager
def stage(name):
    p = _active.get()
    if p is None:
        yield
    else:
        with p.span(name):
            yield


@contextmanager
def measured():
    from app import extraction
    from . import pipeline_v4 as v4, pipeline_v5 as v5
    p = Profile()
    patches = []

    def install(obj, attr, name):
        original = getattr(obj, attr)
        @wraps(original)
        def wrapped(*args, **kwargs):
            label = name
            if name == 'v5.region':
                label += '.' + str(args[2] if len(args)>2 else kwargs.get('tag','unknown'))
            with stage(label):
                return original(*args, **kwargs)
        patches.append((obj, attr, original))
        setattr(obj, attr, wrapped)

    with _lock:
        token = _active.set(p)
        try:
            for attr in ('image_to_data', 'image_to_string', 'image_to_osd'):
                install(extraction.pytesseract, attr, 'engine.'+attr)
            for attr in ('text_from_file', 'extract_fields', 'extract_line_items', 'validate'):
                install(extraction, attr, 'current.'+attr)
            for attr in ('extract_v4', 'prepare', 'recognize', 'field_context', 'parse_table'):
                install(v4, attr, 'v4.'+attr)
            for attr in ('extract_v5', 'paper_view', 'numeric_reread', 'refine_fields', 'improve_cells', 'choose_fields'):
                install(v5, attr, 'v5.'+attr)
            install(v5, 'ocr_region', 'v5.region')
            yield p
        finally:
            for obj, attr, original in reversed(patches):
                setattr(obj, attr, original)
            _active.reset(token)


@contextmanager
def capture_v4_rasters():
    """Retain the exact raster already prepared by V4, not another OCR pass.

    This hook is limited to the same serial offline lock as profiling. Copies
    live for one document and are closed by the caller. No disk/cache reuse.
    """
    from . import pipeline_v4 as v4
    pages = []
    with _lock:
        original = v4.prepare
        def prepare(image):
            raster, info = original(image)
            pages.append(raster.copy())
            return raster, info
        v4.prepare = prepare
        try:
            yield pages
        finally:
            v4.prepare = original
