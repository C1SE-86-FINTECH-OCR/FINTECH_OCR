"""Optional local PP-OCRv5 worker and conservative independent-source merge.

Worker runs in a separate supported Python environment. Only preinstalled local
weights and raster pixels passed through stdin are used during recognition.
No invoice files are sent to a remote service, or written to temporary files.
"""
from pathlib import Path
import base64
import atexit
from contextlib import redirect_stdout
from io import BytesIO
import json
import math
import os
import subprocess
from queue import Queue, Empty
from threading import Lock, Thread
import sys
from time import monotonic

DET = 'PP-OCRv5_mobile_det'
REC = 'latin_PP-OCRv5_mobile_rec'
FILES = ('inference.json', 'inference.pdiparams', 'inference.yml')
MAX_INPUT = 64 * 1024 * 1024
MAX_BOXES = 12000
MAX_REPLY = 64 * 1024 * 1024
TABLE_MODELS = {
    'table_classification': 'PP-LCNet_x1_0_table_cls',
    'wired_table_structure_recognition': 'SLANet_plus',
    'wireless_table_structure_recognition': 'SLANet_plus',
    'wired_table_cells_detection': 'RT-DETR-L_wired_table_cell_det',
    'wireless_table_cells_detection': 'RT-DETR-L_wireless_table_cell_det',
}



def _request_stream(persistent):
    """One JSON document per line in serve mode; keep the original CLI mode."""
    while True:
        raw = (sys.stdin.buffer.readline(MAX_INPUT + 2) if persistent
               else sys.stdin.buffer.read(MAX_INPUT + 1))
        if not raw:
            return
        if persistent:
            if not raw.endswith(b'\n'):
                raise ValueError('Incomplete local AI request frame')
            raw = raw[:-1]
        if len(raw) > MAX_INPUT:
            raise ValueError('Local AI input limit exceeded')
        request = json.loads(raw)
        del raw
        if not isinstance(request, list) or not 1 <= len(request) <= 12:
            raise ValueError('Invalid page count')
        yield request
        del request
        if not persistent:
            return


def _emit_result(marker, result):
    # Newline first isolates any native-library progress output from protocol.
    reply = marker + json.dumps(result, ensure_ascii=True, allow_nan=False)
    if len(reply) + 4 > MAX_REPLY:
        raise ValueError('Local AI reply limit exceeded')
    print('\n' + reply, flush=True)


class _ModelProcess:
    """One isolated, serial worker per model family, scoped to this API process."""
    def __init__(self, flag, marker):
        self.flag = flag
        self.marker = marker
        self.lock = Lock()
        self.process = None
        self.key = None

    def close(self):
        proc, self.process, self.key = self.process, None, None
        if proc is None:
            return
        if proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
        try:
            proc.wait(timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            return

    def request(self, executable, root, threads, payload, timeout, env):
        if len(payload) > MAX_INPUT or b'\n' in payload:
            raise ValueError('Invalid local AI request frame')
        deadline = monotonic() + timeout
        if not self.lock.acquire(timeout=timeout):
            # A concurrent upload owns the worker; do not kill its inference.
            raise TimeoutError('Local AI worker busy')
        try:
            if monotonic() >= deadline:
                raise TimeoutError('Local AI worker busy')
            key = (str(executable), str(root), int(threads), tuple(sorted(env.items())))
            if self.process is None or self.process.poll() is not None or self.key != key:
                self.close()
                self.process = subprocess.Popen(
                    [key[0], str(Path(__file__).resolve()), self.flag, key[1], str(threads)],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                self.key = key
            proc = self.process
            result = Queue(maxsize=1)

            def exchange():
                try:
                    proc.stdin.write(payload + b'\n')
                    proc.stdin.flush()
                    remaining = MAX_REPLY
                    while remaining > 0:
                        line = proc.stdout.readline(remaining + 1)
                        if not line or len(line) > remaining or not line.endswith(b'\n'):
                            raise ValueError('Invalid local AI response frame')
                        remaining -= len(line)
                        if line.startswith(self.marker):
                            result.put((True, json.loads(line[len(self.marker):])))
                            return
                    raise ValueError('Local AI reply limit exceeded')
                except Exception as exc:
                    result.put((False, exc))

            io = Thread(target=exchange, daemon=True)
            io.start()
            try:
                ok, value = result.get(timeout=max(0, deadline - monotonic()))
                if not ok:
                    raise value
                return value
            except Empty as exc:
                self.close()
                raise TimeoutError('Local AI worker timed out') from exc
            except Exception:
                self.close()
                raise
            finally:
                # Killing the child closes its pipe ends, releasing blocked I/O.
                # A broken worker is never reused, even if its thread is late.
                if self.process is not proc:
                    io.join(timeout=1)
                    if not io.is_alive():
                        for pipe in (proc.stdin, proc.stdout):
                            try:
                                pipe.close()
                            except OSError:
                                pass
        finally:
            self.lock.release()


_OCR_PROCESS = _ModelProcess('--serve', b'FINTECH_LOCAL_OCR_RESULT=')
_TABLE_PROCESS = _ModelProcess('--serve-table', b'FINTECH_LOCAL_TABLE_RESULT=')
atexit.register(_OCR_PROCESS.close)
atexit.register(_TABLE_PROCESS.close)


def model_paths(root):
    paths = tuple(Path(root).resolve() / name for name in (DET, REC))
    if not all((path / name).is_file() and (path / name).stat().st_size > 0
               for path in paths for name in FILES):
        raise FileNotFoundError('Local PaddleOCR weights are incomplete')
    return paths


def prepare_models(root):
    # Explicit setup only, no invoice input. Never download from the upload path.
    from huggingface_hub import snapshot_download
    for name in (DET, REC):
        snapshot_download(repo_id='PaddlePaddle/' + name, local_dir=str(Path(root) / name),
                          allow_patterns=list(FILES) + ['config.json'], token=False)
    det, rec = model_paths(root)
    os.environ.update(HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
                      PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True', DISABLE_MODEL_SOURCE_CHECK='True')
    from layout import paddle_reader
    _, version = paddle_reader(det, rec, 'cpu', 4)
    print(f'Local PaddleOCR model initialized; PaddlePaddle {version}')


def table_model_paths(root):
    paths = {role: Path(root).resolve() / name for role, name in TABLE_MODELS.items()}
    if not all((path / name).is_file() and (path / name).stat().st_size > 0
               for path in paths.values() for name in FILES):
        raise FileNotFoundError('Local table recognition weights are incomplete')
    return paths


def table_reader(root, threads):
    # The table branch of PP-StructureV3, with only the active models loaded.
    # Explicit local paths prevent fetching weights during invoice processing.
    os.environ.update(HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
                      PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True', DISABLE_MODEL_SOURCE_CHECK='True')
    from paddleocr import TableRecognitionPipelineV2
    det, rec = model_paths(root)
    paths = table_model_paths(root)
    kwargs = {role + '_model_name': name for role, name in TABLE_MODELS.items()}
    kwargs.update({role + '_model_dir': str(path) for role, path in paths.items()})
    return TableRecognitionPipelineV2(
        **kwargs, text_detection_model_name=DET, text_detection_model_dir=str(det),
        text_recognition_model_name=REC, text_recognition_model_dir=str(rec),
        use_doc_orientation_classify=False, use_doc_unwarping=False,
        use_layout_detection=False, use_ocr_model=True, device='cpu',
        enable_mkldnn=False, cpu_threads=threads)


def prepare_table_models(root):
    from huggingface_hub import snapshot_download
    model_paths(root)
    for name in dict.fromkeys(TABLE_MODELS.values()):
        snapshot_download(repo_id='PaddlePaddle/' + name, local_dir=str(Path(root) / name),
                          allow_patterns=list(FILES) + ['config.json'], token=False)
    table_reader(root, 4)
    print('Local table recognition models initialized')


def table_band(raster, reads, inherited=None):
    """Crop an observed table, including a bounded continuation without a footer."""
    from . import refine_v8 as refine
    from .table_v3 import column_index
    aligned = [r for r in reads if r.boxes and tuple(r.size) == raster.size
               and r.transform.get('coordinate_space') == 'V4 processed raster pixels']
    for read in aligned:
        own = refine.grid.header_for(read)
        header = own or inherited
        if not header or not {'description', 'amount'}.issubset(header.centers):
            continue
        zone = refine.safe_zone(read, header)
        h = max(3, zone['h'])
        bottom = min(raster.height, math.ceil(zone['footer_start']))
        if own and bottom < raster.height:
            top = max(0, math.floor(own.bottom - 3*h))
            if bottom-top > 3*h:
                return (0, top, raster.width, bottom), 'labelled'
        # No observed footer or no repeated header. Require actual selling
        # rows from this same raster, not extrapolated rows or the page edge.
        rows, _ = refine.positioned_rows(read, zone, header)
        if len(rows) < (1 if own else 2):
            continue
        known = {(box.text, box.polygon) for box in read.boxes}
        points, anchors = [], []
        for row in rows:
            evidence = row.get('evidence', {})
            roles = ('description', 'amount') if own else ('description', 'quantity', 'unit_price', 'amount')
            if any(row.get(k) is None or not evidence.get(k) for k in roles):
                break
            parts = [part for k in roles for part in evidence[k]]
            if any(not part.get('polygon') or
                   (part['text'], tuple(map(tuple, part['polygon']))) not in known for part in parts):
                break
            # A continuation must have separately observed numeric columns
            # at the inherited horizontal positions, not just a similar name.
            if not own and any(column_index(header, sum(x for x,y in part['polygon'])/len(part['polygon']),
                                            raster.width) != k
                               for k in roles[1:] for part in evidence[k]):
                break
            row_points = [point for part in parts for point in part['polygon']]
            if not all(0 <= x <= raster.width and header.bottom <= y < bottom for x,y in row_points):
                break
            points.extend(row_points)
            anchors.append(row['_y'])
        else:
            if len(set(anchors)) != len(rows) or not points:
                continue
            top = max(0, math.floor(own.bottom-3*h if own else min(y for x,y in points)-.6*h))
            end = min(bottom, math.ceil(max(y for x,y in points)+.6*h))
            if end-top > h:
                return (0, top, raster.width, end), 'labelled_bounded' if own else 'continuation'
    return None, None


def _table_predict(request, model):
    output = []
    with redirect_stdout(sys.stderr):
        import numpy as np
        from PIL import Image
        for page in request:
            try:
                raw = base64.b64decode(page['image'], validate=True)
                with Image.open(BytesIO(raw)) as image:
                    if image.width * image.height > 8_000_000:
                        raise ValueError('Table raster too large')
                    with image.convert('RGB') as rgb:
                        result = list(model.predict(np.asarray(rgb)[:, :, ::-1].copy(),
                                                    use_table_orientation_classify=False,
                                                    use_ocr_results_with_table_cells=True))
                        if len(result) != 1:
                            raise ValueError('Expected one table result')
                        data = result[0].json
                        tables = data.get('res', data).get('table_res_list', [])
                        if len(tables) != 1:
                            raise ValueError('Expected one cropped table')
                        table = tables[0]
                        # Use real cell geometry and OCR polygons, not HTML text or
                        # guessed positions. Reject text spanning several cells.
                        cells = []
                        for raw_cell in table.get('cell_box_list', []):
                            values = np.asarray(raw_cell, dtype=float).reshape(-1)
                            if len(values) == 4:
                                x0,y0,x1,y1 = values.tolist()
                            elif len(values) == 8:
                                pts = values.reshape(4,2)
                                x0,y0 = pts.min(axis=0).tolist()
                                x1,y1 = pts.max(axis=0).tolist()
                            else:
                                continue
                            if (0 <= x0 < x1 <= rgb.width+1 and 0 <= y0 < y1 <= rgb.height+1):
                                cells.append((x0,y0,x1,y1))
                        cells = list(dict.fromkeys(cells))
                        if not 1 <= len(cells) <= 2000:
                            raise ValueError('Invalid cell geometry')
                        ocr = table.get('table_ocr_pred', {})
                        boxes = []
                        for text, polygon, score in zip(ocr['rec_texts'], ocr['rec_polys'], ocr['rec_scores'], strict=True):
                            pts = np.asarray(polygon, dtype=float)
                            if pts.shape != (4,2) or not np.isfinite(pts).all():
                                continue
                            x0,y0 = pts.min(axis=0).tolist()
                            x1,y1 = pts.max(axis=0).tolist()
                            if not (0 <= x0 < x1 <= rgb.width and 0 <= y0 < y1 <= rgb.height):
                                continue
                            owners = [cell for cell in cells if cell[0]-2 <= x0 and cell[1]-2 <= y0
                                      and x1 <= cell[2]+2 and y1 <= cell[3]+2]
                            if len(owners) != 1 or not str(text).strip() or not 0 <= float(score) <= 1:
                                continue
                            boxes.append({'text': str(text), 'polygon': pts.tolist(), 'score': float(score)})
                        if not boxes or len(boxes) > MAX_BOXES:
                            raise ValueError('No uniquely owned table OCR boxes')
                        output.append({'page': page['page'], 'boxes': boxes, 'cells': len(cells)})
            except Exception as exc:
                output.append({'page': page['page'], 'error_type': type(exc).__name__})
    return output


def table_worker(root, threads, persistent=False):
    model = None
    for request in _request_stream(persistent):
        if model is None:
            with redirect_stdout(sys.stderr):
                model = table_reader(root, threads)
        _emit_result('FINTECH_LOCAL_TABLE_RESULT=', _table_predict(request, model))
        del request


def recognize_tables(pages, rasters, reads, config, layout, env, document_number=None):
    """Optional cell-aware read. Existing Paddle reads survive all failures."""
    from PIL import Image
    from . import refine_v8 as refine, pipeline_v4 as v4, pipeline_v5 as v5
    from .layout import TextBox
    from .table_state_v8_final import continuation_header, next_table_state
    request, frames, summary = [], {}, {}
    encoded_size = 0
    carried = None
    try:
        table_model_paths(config['models'])
        for page, raster in zip(pages, rasters, strict=True):
            number = page['page']
            if number not in reads:
                carried = None
                continue
            try:
                aligned = [r for r in refine.page_reads(layout, page) if r.boxes and tuple(r.size) == raster.size
                           and r.transform.get('coordinate_space') == 'V4 processed raster pixels']
                inherited, notes = continuation_header(carried, aligned, number)
                if any(n['code'] in ('V8_FINAL_CONTINUATION_IDENTIFIER_CONFLICT',
                                     'V8_FINAL_CONTINUATION_IDENTIFIER_UNESTABLISHED') for n in notes):
                    carried = None
                    summary[number] = {'status': 'region_unconfirmed', 'reason': 'identifier_conflict'}
                    continue
                # A headerless page is eligible only with known document identity
                # and the existing continuation check (adjacency and frame).
                if not document_number:
                    inherited = None
                band, kind = table_band(raster, aligned, inherited)
                carried = None
                if band and aligned:
                    observed, _ = refine.recover_rows(aligned, [], inherited)
                    carried = next_table_state(aligned, observed, number, document_number,
                                               refine.table_header(aligned, inherited))
            except Exception as exc:
                carried = None
                summary[number] = {'status': 'region_unconfirmed', 'reason': type(exc).__name__}
                continue
            if not band:
                summary[number] = {'status': 'region_unconfirmed'}
                continue
            with raster.crop(band).convert('RGB') as crop:
                crop.thumbnail((2600,2600), Image.Resampling.LANCZOS)
                size = crop.size
                with BytesIO() as buffer:
                    crop.save(buffer, format='PNG')
                    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
            if encoded_size + len(encoded) > MAX_INPUT - 4096:
                summary[number] = {'status': 'input_limit'}
                continue
            encoded_size += len(encoded)
            request.append({'page': number, 'image': encoded})
            frames[number] = (band, size, raster.size, kind)
        if not request:
            return summary
        payload = json.dumps(request, separators=(',', ':')).encode('ascii')
        results = _TABLE_PROCESS.request(Path(config['python']), config['models'],
                                         config.get('threads', 4), payload,
                                         config.get('timeout', 120), env)
        if [r['page'] for r in results] != [r['page'] for r in request]:
            raise ValueError('Local table response sequence mismatch')
        for item in results:
            number = item['page']
            if item.get('error_type'):
                summary[number] = {'status': 'failed', 'reason': item['error_type']}
                continue
            try:
                (x0,y0,x1,y1), (w,h), raster_size, kind = frames[number]
                sx,sy = (x1-x0)/w, (y1-y0)/h
                boxes = []
                if len(item['boxes']) > MAX_BOXES:
                    raise ValueError('Too many table boxes')
                for box in item['boxes']:
                    points = tuple((float(x),float(y)) for x,y in box['polygon'])
                    text, score = box['text'].strip(), float(box['score'])
                    if (not text or len(text)>2000 or len(points)!=4 or not 0<=score<=1
                            or not all(0<=x<=w and 0<=y<=h for x,y in points)):
                        continue
                    boxes.append(TextBox(text,tuple((x0+x*sx,y0+y*sy) for x,y in points),score))
                if not boxes:
                    raise ValueError('No usable table boxes')
                reads[number].refined = {**(reads[number].refined or {}), 'table_boxes': [{'text': b.text, 'polygon': b.polygon, 'score': b.score}
                                                         for b in boxes],
                                         'table_band': (x0,y0,x1,y1), 'table_region_kind': kind}
                summary[number] = {'status':'read','cells':item['cells'],'boxes':len(boxes), 'region_kind': kind}
            except (TypeError, ValueError, KeyError, OverflowError) as exc:
                summary[number] = {'status':'failed','reason':type(exc).__name__}
    except Exception as exc:
        for page in pages:
            if page['page'] in reads:
                summary.setdefault(page['page'], {'status':'failed','reason':type(exc).__name__})
    return summary


def description_band(raster, reads):
    """Isolate description using aligned header labels and observed body rows.

    A footer gap must not dilute a real separator. If the rules are faint or
    absent, use only a gutter supported by separate STT/name/unit observations.
    """
    import re
    from PIL import Image
    from . import refine_v8 as refine
    aligned = [read for read in reads if tuple(read.size) == raster.size and read.boxes
               and read.transform.get('coordinate_space') == 'V4 processed raster pixels']
    shared = refine.table_header(aligned)
    required = {'ordinal', 'description', 'unit', 'amount'}
    w, height = raster.size
    for read in aligned:
        own = refine.grid.header_for(read)
        header = own if own and required.issubset(own.centers) else shared
        if not header or not required.issubset(header.centers):
            continue
        ordinal, desc, unit = (header.centers[k] * w for k in ('ordinal', 'description', 'unit'))
        if not 0 <= ordinal < desc < unit < w:
            continue
        zone = refine.safe_zone(read, header)
        h = max(3, zone['h'])
        if min(desc-ordinal, unit-desc) < h:
            continue
        try:
            rows, _ = refine.positioned_rows(read, zone, header)
        except (ValueError, KeyError, IndexError, TypeError):
            continue
        body = []
        for row in rows:
            ev = row.get('evidence', {})
            name = [p for p in ev.get('description', []) if p.get('polygon')]
            amount = [p for p in ev.get('amount', []) if p.get('polygon')]
            if not name or not amount or row.get('amount') is None:
                continue
            points = [p for part in [*name, *amount] for p in part['polygon']]
            ys = [p[1] for p in points]
            if min(ys) <= header.bottom or max(ys) >= zone['footer_start']:
                continue
            body.append((row, name, amount, min(ys), max(ys)))
        if len(body) < 2:
            continue
        # Limit the projection to selling rows rather than the gap above totals.
        top = max(0, math.ceil(header.bottom + 1), math.floor(min(r[3] for r in body) - h/2))
        bottom = min(height, math.floor(zone['footer_start']), math.ceil(max(r[4] for r in body) + h/2))
        if bottom-top < 3*h:
            continue
        with raster.crop((0, top, w, bottom)).convert('L') as region:
            with region.point(lambda p: 255 if p < 235 else 0) as mask:
                projection = list(mask.resize((w, 1), Image.Resampling.BOX).getdata())
        def separator(a, b):
            runs = []
            for x in range(max(0, math.ceil(a)), min(w, math.floor(b))):
                if projection[x] < 192:
                    continue
                if runs and x == runs[-1][-1]+1:
                    runs[-1].append(x)
                else:
                    runs.append([x])
            if len(runs) != 1 or len(runs[0]) > max(3, .15*(b-a)):
                return None
            return runs[0][0], runs[0][-1]
        left, right = separator(ordinal, desc), separator(desc, unit)
        if left and right and right[0]-left[1] > 3*h:
            x0, x1 = left[1]+1, right[0]
            if all(x0 <= x <= x1 for _, name, _, _, _ in body for part in name for x, _ in part['polygon']):
                return (x0, top, x1, bottom)
        # A fallback for faded/absent rules. Every selected row must have a
        # separately observed ordinal and unit, with a common non-overlapping
        # gutter. Never split a recognized line by character count.
        left_edges, right_edges, names = [], [], []
        for row, name, amount, _, _ in body:
            y = sum(p[1] for part in amount for p in part['polygon']) / sum(len(part['polygon']) for part in amount)
            ordinals = [box for box in read.boxes if re.fullmatch(r'\d{1,4}[.)]?', box.text.strip())
                        and abs((box.word[1]+box.word[3])/2-y) <= h
                        and abs((box.word[0]+box.word[2])/2-ordinal) <= h]
            units = [p for p in row.get('evidence', {}).get('unit', []) if p.get('polygon')]
            if len(ordinals) != 1 or not units or any(abs(sum(y0 for _, y0 in p['polygon'])/len(p['polygon'])-y) > h for p in units):
                break
            left_edges.append(ordinals[0].word[2])
            right_edges.append(min(x for p in units for x, _ in p['polygon']))
            names.extend(name)
        else:
            pad = max(2, .2*h)
            x0, x1 = math.ceil(max(left_edges)+pad), math.floor(min(right_edges)-pad)
            if (ordinal < x0 < desc < x1 < unit and x1-x0 > 3*h
                    and all(x0 <= x <= x1 for p in names for x, _ in p['polygon'])
                    and not any(top <= (box.word[1]+box.word[3])/2 < bottom
                                and (box.word[0] < x0 < box.word[2] or box.word[0] < x1 < box.word[2])
                                for box in read.boxes)):
                return (x0, top, x1, bottom)
    return None


def _crosses_band(polygon, band):
    x0, y0, x1, y1 = band
    xs, ys = zip(*polygon)
    # The actual box must intersect the description column and extend beyond
    # a real separator. Small detector padding is not a cross-column merge.
    return (y0 <= (min(ys)+max(ys))/2 < y1 and min(xs) < x1 and max(xs) > x0
            and (min(xs) < x0-3 or max(xs) > x1+3))


def _ocr_predict(request, recognize, version):
    with redirect_stdout(sys.stderr):
        from PIL import Image
        output = []
        for page in request:
            try:
                image_bytes = base64.b64decode(page['image'], validate=True)
                with Image.open(BytesIO(image_bytes)) as image:
                    if image.width * image.height > 8_000_000:
                        raise ValueError('Local OCR raster too large')
                    with image.convert('RGB') as rgb:
                        boxes = recognize(rgb)
                        entry = {'page': page['page'], 'boxes': [
                            {'text': b.text, 'polygon': b.polygon, 'score': b.score} for b in boxes]}
                        band = page.get('description_band')
                        if band and len(band) == 4:
                            x0, y0, x1, y1 = band
                            if 0 <= x0 < x1 <= rgb.width and 0 <= y0 < y1 <= rgb.height:
                                try:
                                    # One independent column read per page, using the same model.
                                    # Prefer original raster pixels, not an enlarged page thumbnail.
                                    if page.get('description_image'):
                                        raw = base64.b64decode(page['description_image'], validate=True)
                                        with Image.open(BytesIO(raw)) as crop:
                                            if crop.width * crop.height > 8_000_000:
                                                raise ValueError('Local OCR crop too large')
                                            with crop.convert('RGB') as enlarged:
                                                sx, sy = (x1-x0)/enlarged.width, (y1-y0)/enlarged.height
                                                isolated = recognize(enlarged)
                                    else:
                                        with rgb.crop(band) as crop:
                                            scale = min(2., 2600/max(crop.size))
                                            with crop.resize((max(1, round(crop.width*scale)),
                                                              max(1, round(crop.height*scale))), Image.Resampling.LANCZOS) as enlarged:
                                                sx, sy = crop.width/enlarged.width, crop.height/enlarged.height
                                                isolated = recognize(enlarged)
                                    if len(isolated) > MAX_BOXES:
                                        raise ValueError('Local OCR crop box limit exceeded')
                                    entry['description_crop'] = [
                                        {'text': b.text, 'polygon': [(x0+x*sx, y0+y*sy) for x,y in b.polygon],
                                         'score': b.score} for b in isolated]
                                except Exception as exc:
                                    entry['description_crop_error'] = type(exc).__name__
                if len(boxes) > MAX_BOXES:
                    raise ValueError('Local OCR box limit exceeded')
                output.append(entry)
            except Exception as exc:
                output.append({'page': page['page'], 'error_type': type(exc).__name__})
    return {'version': version, 'pages': output}


def worker(root, threads, persistent=False):
    # Set before importing PaddleX/HF. Never fetch models on invoice upload.
    os.environ.update(HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
                      PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True',
                      DISABLE_MODEL_SOURCE_CHECK='True')
    recognize = None
    for request in _request_stream(persistent):
        if recognize is None:
            try:
                with redirect_stdout(sys.stderr):
                    from layout import paddle_reader
                    det, rec = model_paths(root)
                    recognize, version = paddle_reader(det, rec, 'cpu', threads)
            except Exception as exc:
                _emit_result('FINTECH_LOCAL_OCR_RESULT=', {'version': 'unavailable', 'pages': [
                    {'page': page['page'], 'error_type': 'model_init_' + type(exc).__name__}
                    for page in request]})
                return
        _emit_result('FINTECH_LOCAL_OCR_RESULT=', _ocr_predict(request, recognize, version))
        del request


def worker_environment():
    """Reuse the same local-only environment for independent photo recovery."""
    allowed = {'SYSTEMROOT', 'WINDIR', 'PATH', 'PATHEXT', 'SYSTEMDRIVE', 'COMSPEC',
               'USERPROFILE', 'HOME', 'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP', 'PROGRAMDATA',
               'PROGRAMFILES', 'PROGRAMFILES(X86)', 'NUMBER_OF_PROCESSORS', 'PROCESSOR_ARCHITECTURE'}
    env = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    env.update(PYTHONIOENCODING='utf-8', HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
               PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True', DISABLE_MODEL_SOURCE_CHECK='True')
    return env


def recognize_document(pages, rasters, config, layout=None, document_number=None):
    """Reuse one local OCR model process across documents and eligible pages."""
    from .layout import TextBox
    from . import pipeline_v4 as v4, pipeline_v5 as v5, refine_v8 as refine
    status = {'provider': 'paddleocr-local', 'status': 'not_needed', 'pages': [],
              'fields_filled': 0, 'fields_corrected': 0, 'cells_filled': 0,
              'cells_corrected': 0, 'rows_recovered': 0, 'conflicts': 0}
    reads = {}
    raster_pages = [page for page in pages if page.get('source') == 'ocr']
    if not raster_pages:
        return reads, status
    if len(raster_pages) != len(rasters):
        return reads, {**status, 'status': 'failed', 'reason': 'raster_sequence_unconfirmed'}
    started = monotonic()
    try:
        executable = Path(config['python'])
        root = Path(config['models'])
        if not executable.is_absolute() or not executable.is_file() or not root.is_absolute():
            raise FileNotFoundError('Local OCR interpreter/model path invalid')
        model_paths(root)
        request, frames, bands, encoded_size = [], {}, {}, 0
        for page, raster in zip(raster_pages, rasters, strict=True):
            number = page['page']
            if tuple(page['size']) != raster.size:
                status['pages'].append({'page': number, 'status': 'failed', 'reason': 'raster_frame_mismatch'})
                continue
            # Real resampling with inverse coordinate mapping; never invent word positions.
            with raster.convert('RGB') as image:
                from PIL import Image
                image.thumbnail((2600, 2600), Image.Resampling.LANCZOS)
                width, height = image.size
                with BytesIO() as buffer:
                    image.save(buffer, format='PNG')
                    encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
            if encoded_size + len(encoded) > MAX_INPUT - 4096:
                status['pages'].append({'page': number, 'status': 'failed', 'reason': 'document_input_limit'})
                continue
            encoded_size += len(encoded)
            entry = {'page': number, 'image': encoded}
            # Column isolation is optional: any uncertainty leaves the original
            # full-page OCR and its conflict warnings unchanged.
            if layout is not None:
                try:
                    band = description_band(raster, refine.page_reads(layout, page))
                    if band:
                        x0,y0,x1,y1 = band
                        mapped = (math.ceil(x0*width/raster.width), math.ceil(y0*height/raster.height),
                                  math.floor(x1*width/raster.width), math.floor(y1*height/raster.height))
                        if mapped[2] > mapped[0] and mapped[3] > mapped[1]:
                            entry['description_band'] = mapped
                            bands[number] = mapped
                            # Crop the original raster before page downsampling. Map
                            # the actual crop boundaries back through the same frame.
                            with raster.crop(band).convert('RGB') as crop:
                                scale = min(2., 3000/max(crop.size),
                                            (8_000_000/(crop.width*crop.height))**.5)
                                with crop.resize((max(1, round(crop.width*scale)),
                                                  max(1, round(crop.height*scale))), Image.Resampling.LANCZOS) as high_res:
                                    with BytesIO() as buffer:
                                        high_res.save(buffer, format='PNG')
                                        crop_encoded = base64.b64encode(buffer.getvalue()).decode('ascii')
                            if encoded_size + len(crop_encoded) <= MAX_INPUT - 4096:
                                exact_band = (x0*width/raster.width, y0*height/raster.height,
                                              x1*width/raster.width, y1*height/raster.height)
                                entry['description_image'] = crop_encoded
                                entry['description_band'] = exact_band
                                bands[number] = exact_band
                                encoded_size += len(crop_encoded)
                except Exception:
                    pass
            request.append(entry)
            frames[number] = (raster.size, (width, height))
        if not request:
            raise ValueError('No usable raster frames')
        payload = json.dumps(request, separators=(',', ':')).encode('ascii')
        if len(payload) > MAX_INPUT:
            raise ValueError('Local OCR document input limit exceeded')
        # Do not pass application API keys or DB configuration to the worker.
        env = worker_environment()
        output = _OCR_PROCESS.request(executable, root, config.get('threads', 4),
                                      payload, config.get('timeout', 120), env)
        if [entry['page'] for entry in output['pages']] != [entry['page'] for entry in request]:
            raise ValueError('Local OCR page sequence mismatch')
        status['version'] = str(output['version'])[:40]
        for entry in output['pages']:
            number = entry['page']
            if entry.get('error_type'):
                status['pages'].append({'page': number, 'status': 'failed', 'reason': str(entry['error_type'])[:80]})
                continue
            try:
                size, input_size = frames[number]
                sx, sy = size[0] / input_size[0], size[1] / input_size[1]
                def mapped_boxes(raw, bounds):
                    if len(raw) > MAX_BOXES:
                        raise ValueError('Too many boxes')
                    x0,y0,x1,y1 = bounds
                    boxes = []
                    for box in raw:
                        text = box['text'].strip()
                        score = float(box['score'])
                        points = tuple((float(x), float(y)) for x, y in box['polygon'])
                        if (not text or len(text) > 2000 or len(points) != 4 or not 0 <= score <= 1
                                or not all(math.isfinite(x) and math.isfinite(y) and
                                           x0-1 <= x <= x1+1 and y0-1 <= y <= y1+1 for x, y in points)):
                            continue
                        polygon = tuple((min(size[0], max(0, x*sx)), min(size[1], max(0, y*sy))) for x, y in points)
                        if max(x for x,y in polygon) <= min(x for x,y in polygon) or max(y for x,y in polygon) <= min(y for x,y in polygon):
                            continue
                        boxes.append(TextBox(text, polygon, score))
                    return boxes
                boxes = mapped_boxes(entry['boxes'], (0,0,*input_size))
                if not boxes:
                    raise ValueError('No usable boxes')
                read = v5.Read('paddle-local', boxes, [line.ids for line in v4.lines_of(boxes)], size,
                               {'coordinate_space': 'V4 processed raster pixels', 'engine': 'paddleocr-local'})
                reads[number] = read
                if number in bands:
                    x0,y0,x1,y1 = bands[number]
                    read.refined = {'description_band': (x0*sx,y0*sy,x1*sx,y1*sy), 'description_crop': [],
                                    'description_crop_error': entry.get('description_crop_error')}
                    try:
                        isolated = mapped_boxes(entry.get('description_crop', []), bands[number])
                        read.refined['description_crop'] = [
                            {'text': b.text, 'polygon': b.polygon, 'ocr_score': b.score} for b in isolated]
                    except (ValueError, TypeError, KeyError, OverflowError):
                        pass
                status['pages'].append({'page': number, 'status': 'read', 'boxes': len(boxes),
                                        'description_isolation': ('read' if (read.refined or {}).get('description_crop') else
                                                                  'crop_failed' if entry.get('description_crop_error') else
                                                                  'no_crop_result' if number in bands else 'band_unavailable')})
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                status['pages'].append({'page': number, 'status': 'failed', 'reason': type(exc).__name__})
        status['status'] = 'completed' if len(reads) == len(raster_pages) else 'partial' if reads else 'failed'
        if config.get('table_enabled') and reads and layout is not None:
            table_summary = recognize_tables(raster_pages, rasters, reads, config, layout, env, document_number)
            for page_status in status['pages']:
                if page_status['page'] in table_summary:
                    page_status['table_ai'] = table_summary[page_status['page']]
    except Exception as exc:
        # No automatic cloud retry or leaking raw model errors/paths to the API.
        reads = {}
        status.update(status='failed', reason=type(exc).__name__)
    status['elapsed_s'] = round(monotonic() - started, 3)
    return reads, status


def _parts_strong(parts, minimum=.90):
    return bool(parts) and all(part.get('polygon') and part.get('ocr_score') is not None
                               and float(part['ocr_score']) >= minimum for part in parts)


def _field_identity(key, value):
    """Do not collapse Vietnamese spelling or leading zeros in identifiers."""
    from decimal import Decimal, InvalidOperation
    from unicodedata import normalize
    if value is None:
        return None
    if key in ('subtotal', 'vat_amount', 'vat_rate', 'total_amount'):
        try:
            number = Decimal(str(value))
            if number.is_finite():
                return number
        except (InvalidOperation, ValueError):
            pass
    return ' '.join(normalize('NFC', str(value)).casefold().split())


def _field_box(parts, raster):
    points = [point for part in parts for point in part.get('polygon', [])]
    if not points or any(not part.get('polygon') for part in parts):
        return None
    if any(not (math.isfinite(x) and math.isfinite(y) and
                0 <= x <= raster.width and 0 <= y <= raster.height) for x, y in points):
        return None
    left, top = min(x for x,y in points), min(y for x,y in points)
    right, bottom = max(x for x,y in points), max(y for x,y in points)
    return (left, top, right, bottom) if right > left and bottom > top else None


def _same_field_region(first, second, raster):
    """Both value and label must overlap; party roles must also overlap."""
    for key in ('evidence', 'label_evidence', 'role_evidence'):
        a, b = first.get(key, []), second.get(key, [])
        if key == 'role_evidence' and not a and not b:
            continue
        x = _field_box(a, raster)
        y = _field_box(b, raster)
        if x is None or y is None:
            return False
        intersection = (max(0, min(x[2], y[2])-max(x[0], y[0])) *
                        max(0, min(x[3], y[3])-max(x[1], y[1])))
        area_x = (x[2]-x[0])*(x[3]-x[1])
        area_y = (y[2]-y[0])*(y[3]-y[1])
        if intersection < .5 * max(area_x, area_y):
            return False
    return True


def _field_readback(key, entry, previous, originals, opposed, frames, layout, budget, document_type):
    """Reread one labelled source region in its original page pixel frame."""
    from . import refine_v8 as refine, pipeline_v5 as v5
    from .document_fields_v8_final import target_observations
    page_number = entry.get('page')
    if budget[0] <= 0 or page_number not in frames:
        return None
    raster, page, local_read = frames[page_number]
    if tuple(local_read.size) != raster.size or local_read.transform.get('coordinate_space') != 'V4 processed raster pixels':
        return None
    def belongs(candidate, reads):
        parts = [part for name in ('evidence', 'label_evidence', 'role_evidence')
                 for part in candidate.get(name, [])]
        if not parts or not candidate.get('label_evidence'):
            return False
        tokens = {(part['text'], tuple(map(tuple, part['polygon']))) for part in parts if part.get('polygon')}
        if any(not part.get('polygon') for part in parts):
            return False
        return any(tokens <= {(box.text, tuple(map(tuple, box.polygon))) for box in read.boxes}
                   for read in reads if tuple(read.size) == raster.size and
                   read.transform.get('coordinate_space') == 'V4 processed raster pixels' and
                   not read.transform.get('trusted_text_layer'))
    reads = refine.page_reads(layout, page)
    if not belongs(entry, [local_read]):
        return None
    same = lambda candidate: (candidate.get('page') == page_number and
                              _field_identity(key, candidate['value']) == _field_identity(key, previous) and
                              _same_field_region(candidate, entry, raster) and belongs(candidate, reads))
    anchors = [candidate for candidate in originals if same(candidate)]
    # A different page, another labelled location or a third value is not a
    # single-cell OCR disagreement. Never resolve it by rereading one crop.
    if not anchors or any(not same(candidate) for candidate in opposed):
        return None
    anchor = max(anchors, key=lambda candidate: candidate.get('score', 0))
    parts = [part for candidate in (anchor, entry)
             for name in ('evidence', 'label_evidence', 'role_evidence')
             for part in candidate.get(name, [])]
    bounds = _field_box(parts, raster)
    if bounds is None:
        return None
    heights = [max(y for x,y in part['polygon']) - min(y for x,y in part['polygon']) for part in parts]
    from statistics import median
    h = max(3, median(heights))
    if bounds[3]-bounds[1] > 8*h:
        return None
    pad = max(2, .15*h)
    bbox = (max(0, math.floor(bounds[0]-pad)), max(0, math.floor(bounds[1]-pad)),
            min(raster.width, math.ceil(bounds[2]+pad)), min(raster.height, math.ceil(bounds[3]+pad)))
    if (bbox[2]-bbox[0])*(bbox[3]-bbox[1]) > 2_000_000:
        return None
    budget[0] -= 1
    read = v5.ocr_region(raster, bbox, f'local-ai-field-verify-{key}', 'vie+eng', 6)
    candidates = target_observations(document_type, refine.field_candidates([read])).get(key, [])
    matches = [candidate for candidate in candidates if candidate.get('priority', 0) >= 2 and
               candidate.get('label_evidence') and _parts_strong(candidate.get('evidence', []), .80) and
               _same_field_region(candidate, entry, raster)]
    if not matches or len({_field_identity(key, candidate['value']) for candidate in matches}) != 1:
        return None
    verified = max(matches, key=lambda candidate: candidate['score'])
    return {**verified, 'page': page_number, 'crop': bbox, 'engine': 'tesseract'}


def merge_fields(fields, baseline, local, status, *, frames=None, layout=None):
    """Fill labelled observations; correct an existing value only with agreement
    from a separate Tesseract read. Unresolved disagreements remain for review.
    Never treat scores from two different engines as calibrated probabilities.
    """
    from .document_fields_v8_final import target_observations
    from app.invoice_financials import party_name_allowed
    existing = target_observations(fields.get('document_type'), baseline)
    proposed = target_observations(fields.get('document_type'), local)
    result, findings = dict(fields), []
    allowed = {'invoice_number', 'invoice_symbol', 'invoice_date', 'seller_name', 'seller_tax_code',
               'buyer_name', 'buyer_tax_code', 'subtotal', 'vat_rate', 'vat_amount', 'total_amount', 'currency'}
    # Bound total extra header/footer OCR time, not a per-field retry loop.
    budget = [3]
    priority = ('invoice_number', 'seller_tax_code', 'buyer_tax_code', 'total_amount',
                'invoice_date', 'invoice_symbol', 'seller_name', 'buyer_name',
                'subtotal', 'vat_amount', 'vat_rate', 'currency')
    for key in priority:
        values = proposed.get(key, [])
        if key not in allowed or not values:
            continue
        ident = lambda value: _field_identity(key, value)
        strong = [entry for entry in values if entry.get('priority', 0) >= 2 and entry.get('score', 0) >= .90
                  and _parts_strong(entry.get('evidence', [])) and entry.get('label_evidence')
                  and (not key.endswith('_name') or party_name_allowed(entry['value']))]
        if not strong:
            continue
        best_priority = max(entry['priority'] for entry in strong)
        strong = [entry for entry in strong if entry['priority'] == best_priority]
        choices = {ident(entry['value']) for entry in strong}
        previous = result.get(key)
        if len(choices) != 1:
            status['conflicts'] += 1
            findings.append({'code': 'LOCAL_AI_FIELD_CONFLICT', 'field': key, 'requires_review': True})
            continue
        entry = max(strong, key=lambda item: item['score'])
        value = entry['value']
        if previous is not None and ident(previous) == ident(value):
            continue
        comparable = [other for other in existing.get(key, [])
                      if other.get('priority', 0) >= best_priority and
                      (other.get('trusted_text_layer') or other.get('score', 0) >= .80)]
        same_page = [other for other in comparable if other.get('page') == entry.get('page')]
        corroborated = any(ident(other['value']) == ident(value) and other.get('evidence')
                           for other in same_page)
        opposed = any(ident(other['value']) != ident(value) for other in comparable)
        trusted_opposed = any(other.get('trusted_text_layer') and ident(other['value']) != ident(value)
                              for other in existing.get(key, []))
        # Never replace a VAT rate amid contradictory observed rates or share a tax ID between parties.
        other_tax = 'buyer_tax_code' if key == 'seller_tax_code' else 'seller_tax_code'
        shared_tax = key.endswith('_tax_code') and result.get(other_tax) and str(result[other_tax]).replace('-', '').replace(' ', '') == str(value).replace('-', '').replace(' ', '')
        verified_alternative = False
        if (previous is not None and (not corroborated or opposed) and frames and layout is not None
                and not shared_tax and not trusted_opposed and not (key == 'vat_rate' and opposed)):
            try:
                verification = _field_readback(key, entry, previous, existing.get(key, []),
                                               [other for other in comparable if ident(other['value']) != ident(value)],
                                               frames, layout, budget, fields.get('document_type'))
                if verification:
                    verified_alternative = ident(verification['value']) == ident(value)
                    findings.append({'code': 'LOCAL_AI_FIELD_VERIFIED', 'field': key, 'page': entry['page'],
                                     'retained': previous, 'alternative': value, 'verification': verification,
                                     'supports_alternative': verified_alternative})
            except Exception as exc:
                findings.append({'code': 'LOCAL_AI_FIELD_READBACK_FAILED', 'field': key,
                                 'page': entry.get('page'), 'error_type': type(exc).__name__,
                                 'requires_review': True})
        if (shared_tax or trusted_opposed or (key == 'vat_rate' and opposed)
                or (previous is None and opposed) or (previous is not None and (not corroborated or opposed)
                                                     and not verified_alternative)):
            status['conflicts'] += 1
            findings.append({'code': 'LOCAL_AI_FIELD_CONFLICT', 'field': key, 'retained': previous,
                             'alternative': value, 'requires_review': True})
            continue
        result[key] = value
        status['fields_filled' if previous is None else 'fields_corrected'] += 1
        findings.append({'code': 'LOCAL_AI_FIELD_ADOPTED', 'field': key, 'before': previous, 'after': value,
                         'reason': ('labelled local AI observation' if previous is None else
                                    'targeted independent OCR readback' if verified_alternative else 'independent OCR agreement'),
                         'requires_review': True})
    return result, findings


def merge_rows(rows, alternative, primary_reads, local_read, status, raster=None):
    """Merge only a one-to-one row with shared coordinates and source identity.
    Do not create words by splitting a line polygon into synthetic token boxes.
    """
    from copy import deepcopy
    from statistics import median
    from . import pipeline_v4 as v4, pipeline_v5 as v5, table_v8 as grid
    from .table_v3 import row_evidence, number, column_index
    from .table_v6 import arithmetic_checks
    result, findings = deepcopy(rows), []
    # Never align a warped or unknown coordinate frame against a captured raster.
    known = {(box.text, box.polygon) for read in primary_reads
             if read.transform.get('coordinate_space') == 'V4 processed raster pixels'
             for box in read.boxes}
    def anchor(row, local=False):
        for key in ('amount', 'unit_price', 'quantity'):
            parts = row.get('evidence', {}).get(key, [])
            if not parts or not all(part.get('polygon') for part in parts):
                continue
            if not local and not all((part['text'], tuple(map(tuple, part['polygon']))) in known for part in parts):
                continue
            ys = [point[1] for part in parts for point in part['polygon']]
            return (min(ys)+max(ys))/2, max(ys)-min(ys)
        return None
    isolated = local_read.refined or {}
    band = isolated.get('description_band')
    crop_parts = isolated.get('description_crop', [])
    def strong_row(row):
        description = row.get('evidence', {}).get('description', [])
        if band and any(_crosses_band(part['polygon'], band) for part in description if part.get('polygon')):
            return False  # A mixed-column name cannot recover an entire missing table.
        return all(row.get(key) is not None and _parts_strong(row.get('evidence', {}).get(key, []))
                   for key in ('description', 'amount'))
    header = grid.header_for(local_read)
    # Recover a wholly missing table only from a labelled grid with source-backed rows.
    if not result and alternative and header and {'description', 'amount'}.issubset(header.centers):
        if all(strong_row(row) for row in alternative) and not arithmetic_checks({}, alternative):
            status['rows_recovered'] += len(alternative)
            return deepcopy(alternative), [{'code': 'LOCAL_AI_TABLE_RECOVERED', 'count': len(alternative), 'requires_review': True}]
    if not alternative:
        if result:
            findings.append({'code': 'LOCAL_AI_TABLE_UNCONFIRMED', 'requires_review': True})
            status['conflicts'] += 1
        return result, findings
    if not result:
        status['conflicts'] += 1
        return result, [{'code': 'LOCAL_AI_TABLE_UNCONFIRMED', 'requires_review': True}]
    lhs, rhs = [anchor(row) for row in result], [anchor(row, True) for row in alternative]
    h = median(box.word[3] - box.word[1] for box in local_read.boxes)
    # Alignment requires unique nearest row and the same description; if OCR
    # spelling differs, two shared numeric cells may establish row identity.
    def compatible(i, j):
        a,b = lhs[i],rhs[j]
        if not a or not b or abs(a[0]-b[0]) > max(3, .55*min(max(a[1],1), max(b[1],1),h)):
            return False
        left,right = result[i],alternative[j]
        left_name = v4.plain(left.get('description') or '')
        same_name = bool(left_name) and left_name == v4.plain(right.get('description') or '')
        same_numbers = sum(left.get(k) is not None and grid.cell_identity(k, left[k]) == grid.cell_identity(k, right.get(k))
                           for k in ('quantity','unit_price','amount'))
        return same_name or same_numbers >= 2
    matches = [[j for j in range(len(alternative)) if compatible(i,j)] for i in range(len(result))]
    used = set()
    verification_budget = 5
    def isolated_description(i, raw_parts, raw_value):
        mixed = bool(band and any(_crosses_band(part['polygon'], band) for part in raw_parts if part.get('polygon')))
        # Missing full-page names can still be recovered from a real column
        # crop when the numeric row is uniquely linked.
        if not band or (not mixed and raw_value is not None):
            return False, None, []
        # No invented splitting of a Paddle line. Assign actual cropped boxes
        # only to an unambiguous, single physical row; wrapped names remain reviewable.
        y, height = lhs[i]
        if any(other is None for other in lhs):
            return True, None, []
        previous = max((other[0] for k,other in enumerate(lhs) if k != i and other[0] < y), default=band[1])
        following = min((other[0] for k,other in enumerate(lhs) if k != i and other[0] > y), default=band[3])
        low = (previous+y)/2 if previous != band[1] else band[1]
        high = (following+y)/2 if following != band[3] else band[3]
        if not low < y < high or any(k != i and abs(other[0]-y) < max(3,height) for k,other in enumerate(lhs)):
            return True, None, []
        def ycenter(part):
            ys = [point[1] for point in part['polygon']]
            return (min(ys)+max(ys))/2
        parts = [part for part in crop_parts if low <= ycenter(part) < high]
        original = result[i].get('evidence', {}).get('description', [])
        tolerance = max(3, .75*max(height, h))
        # A moderately confident crop is eligible for a targeted independent
        # read, but cannot by itself replace or fill a value (see merge below).
        if (not parts or (result[i].get('description') is not None and not original) or not _parts_strong(parts, .80)
                or any(not part.get('polygon') or (part['text'], tuple(map(tuple, part['polygon']))) not in known
                       for part in original)
                or any(min(point[0] for point in part['polygon']) < band[0]-3 or
                       max(point[0] for point in part['polygon']) > band[2]+3 for part in original)
                or any(abs(ycenter(part)-y) > tolerance for part in [*parts, *original])
                or any(min(point[1] for point in part['polygon']) < low or
                       max(point[1] for point in part['polygon']) > high for part in parts)):
            return True, None, []
        parts.sort(key=lambda part: min(point[0] for point in part['polygon']))
        return True, ' '.join(part['text'] for part in parts).strip(), parts
    def verify_description(i, proposed_parts):
        """Independent targeted Tesseract read only for a disputed physical cell."""
        nonlocal verification_budget
        if (verification_budget <= 0 or raster is None or not band or tuple(local_read.size) != raster.size
                or any(other is None for other in lhs)):
            return None
        original = result[i].get('evidence', {}).get('description', [])
        if not original or not all(part.get('polygon') and
                                   (part['text'], tuple(map(tuple, part['polygon']))) in known for part in original):
            return None
        y, height = lhs[i]
        previous = max((a[0] for n,a in enumerate(lhs) if n != i and a[0] < y), default=band[1])
        following = min((a[0] for n,a in enumerate(lhs) if n != i and a[0] > y), default=band[3])
        low = max(band[1], (previous+y)/2 if previous != band[1] else band[1])
        high = min(band[3], (following+y)/2 if following != band[3] else band[3])
        points = [point for part in [*original, *proposed_parts] for point in part.get('polygon', [])]
        if (not points or not low < y < high or any(n != i and abs(a[0]-y) < max(3,height) for n,a in enumerate(lhs))
                or any(not (band[0]-1 <= x <= band[2]+1 and low <= yy <= high) for x,yy in points)):
            return None
        # Use the union of observed name boxes, padded inside the confirmed cell.
        # Reject wrapped names rather than forcing a single-line interpretation.
        if max(yy for _,yy in points)-min(yy for _,yy in points) > 2*max(height,h):
            return None
        pad = max(3, .25*max(height,h))
        bbox = (math.ceil(max(band[0], min(x for x,_ in points)-pad)),
                math.ceil(max(low, min(yy for _,yy in points)-pad)),
                math.floor(min(band[2], max(x for x,_ in points)+pad)),
                math.floor(min(high, max(yy for _,yy in points)+pad)))
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            return None
        verification_budget -= 1
        try:
            read = v5.ocr_region(raster, bbox, f'local-ai-description-verify-{i+1}', 'vie+eng', 7, line_height=True)
            if len(read.lines) != 1:
                return None
            parts = row_evidence(read.boxes, {'value': list(read.lines[0].ids)})['value']
            if not _parts_strong(parts, .80):
                return None
            return {'value': read.lines[0].text.strip(), 'parts': parts, 'read': read.tag,
                    'crop': bbox, 'engine': 'tesseract'}
        except (RuntimeError, ValueError, v5.old.pytesseract.TesseractError):
            return None
    def verify_numeric(i, key, proposed_parts):
        """Reread a disputed printed numeric cell, never infer from arithmetic."""
        nonlocal verification_budget
        if (verification_budget <= 0 or raster is None or tuple(local_read.size) != raster.size
                or header is None or key not in header.centers or any(a is None for a in lhs)):
            return None
        original = result[i].get('evidence', {}).get(key, [])
        if not original or not proposed_parts or not all(
                part.get('polygon') and (part['text'], tuple(map(tuple, part['polygon']))) in known
                for part in original):
            return None
        # Require a matching numeric column in a primary read in the same frame.
        primary_headers = [grid.header_for(read) for read in primary_reads
                           if read.boxes and tuple(read.size) == raster.size
                           and read.transform.get('coordinate_space') == 'V4 processed raster pixels']
        primary_headers = [head for head in primary_headers if head and key in head.centers
                           and {'description', 'amount'}.issubset(head.centers)]
        if not primary_headers:
            return None
        width = raster.width
        if any(abs(head.centers[key] - header.centers[key]) * width > max(3, h)
               for head in primary_headers):
            return None
        y, height = lhs[i]
        before = max((a[0] for n,a in enumerate(lhs) if n != i and a[0] < y), default=header.bottom)
        after = min((a[0] for n,a in enumerate(lhs) if n != i and a[0] > y), default=raster.height)
        low, high = (before+y)/2, (after+y)/2
        if not low < y < high or any(n != i and abs(a[0]-y) < max(3,height) for n,a in enumerate(lhs)):
            return None
        points = [point for part in [*original, *proposed_parts] for point in part.get('polygon', [])]
        if (not points or any(not (0 <= x <= width and low <= yy <= high) for x,yy in points)
                or max(yy for _,yy in points)-min(yy for _,yy in points) > 2*max(height,h)):
            return None
        pad = max(2, .2*max(height,h))
        bbox = (max(0, math.floor(min(x for x,_ in points)-pad)),
                max(math.ceil(low), math.floor(min(yy for _,yy in points)-pad)),
                min(width, math.ceil(max(x for x,_ in points)+pad)),
                min(math.floor(high), math.ceil(max(yy for _,yy in points)+pad)))
        if (bbox[2] <= bbox[0] or bbox[3] <= bbox[1]
                or any(column_index(head, x, width) != key
                       for head in [header, *primary_headers] for x in (bbox[0], bbox[2]-1))):
            return None
        verification_budget -= 1
        try:
            read = v5.ocr_region(raster, bbox, f'local-ai-{key}-verify-{i+1}', 'vie+eng', 7, line_height=True)
            if len(read.lines) != 1:
                return None
            line = read.lines[0]
            parts = row_evidence(read.boxes, {'value': list(line.ids)})['value']
            value = number(line.text.strip(), key)
            if value is None or not value.is_finite() or value < 0 or not _parts_strong(parts, .80):
                return None
            return {'value': value, 'parts': parts, 'read': read.tag, 'crop': bbox,
                    'engine': 'tesseract'}
        except (RuntimeError, ValueError, ArithmeticError, v5.old.pytesseract.TesseractError):
            return None
    for i, choices in enumerate(matches):
        if len(choices) != 1 or sum(choices[0] in other for other in matches) != 1:
            continue
        j = choices[0]; used.add(j)
        row, other = result[i], alternative[j]
        before = deepcopy(row)
        changes = []
        for key in ('description', 'unit', 'quantity', 'unit_price', 'amount'):
            value = other.get(key)
            parts = other.get('evidence', {}).get(key, [])
            previous = row.get(key)
            if key == 'description':
                mixed, reread, isolated_parts = isolated_description(i, parts, value)
                if mixed:
                    if not reread:
                        status['conflicts'] += 1
                        findings.append({'code': 'LOCAL_AI_CELL_CONFLICT', 'line': i+1, 'field': key,
                                         'retained': previous, 'alternative': value,
                                         'reason': 'cross_column_box_isolation_unconfirmed', 'requires_review': True})
                        continue
                    findings.append({'code': 'LOCAL_AI_DESCRIPTION_REREAD', 'line': i+1, 'field': key,
                                     'full_page_alternative': value, 'isolated_alternative': reread,
                                     'evidence': deepcopy(isolated_parts)})
                    value, parts = reread, isolated_parts
            if value is None or grid.cell_identity(key, previous) == grid.cell_identity(key, value):
                continue
            strong_proposal = _parts_strong(parts)
            # Moderate confidence can trigger the existing bounded crop reread,
            # not an uncorroborated fill or a change based only on arithmetic.
            numeric = key in ('quantity', 'unit_price', 'amount')
            eligible_reread = (previous is not None and (key == 'description' or numeric)
                               and _parts_strong(parts, .80))
            if not strong_proposal and not eligible_reread:
                status['conflicts'] += 1
                findings.append({'code': 'LOCAL_AI_CELL_CONFLICT', 'line': i+1, 'field': key,
                                 'retained': previous, 'alternative': value,
                                 'reason': 'weak_local_ai_evidence', 'requires_review': True})
                continue
            # Existing corroboration must belong to the original raster frame,
            # for every field, not only names. A moderate proposal requires an
            # actual targeted reread rather than reuse of existing candidates.
            candidates = row.get('_cell_candidates', {}).get(key, [])
            corroborated = strong_proposal and any(
                grid.cell_identity(key, candidate.get('value')) == grid.cell_identity(key, value)
                and _parts_strong(candidate.get('parts', []), .80)
                and all((part['text'], tuple(map(tuple, part['polygon']))) in known
                        for part in candidate['parts'])
                for candidate in candidates)
            if previous is not None and not corroborated and key == 'description':
                verified = verify_description(i, parts)
                if verified:
                    row.setdefault('_cell_candidates', {}).setdefault(key, []).append(deepcopy(verified))
                    corroborated = grid.cell_identity(key, verified['value']) == grid.cell_identity(key, value)
                    findings.append({'code': 'LOCAL_AI_DESCRIPTION_VERIFIED', 'line': i+1, 'field': key,
                                     'retained': previous, 'alternative': value,
                                     'verification': deepcopy(verified), 'supports_alternative': corroborated})
            if previous is not None and not corroborated and key in ('quantity', 'unit_price', 'amount'):
                verified = verify_numeric(i, key, parts)
                if verified:
                    row.setdefault('_cell_candidates', {}).setdefault(key, []).append(deepcopy(verified))
                    corroborated = grid.cell_identity(key, verified['value']) == grid.cell_identity(key, value)
                    findings.append({'code': 'LOCAL_AI_NUMERIC_VERIFIED', 'line': i+1, 'field': key,
                                     'retained': previous, 'alternative': value,
                                     'verification': deepcopy(verified), 'supports_alternative': corroborated})
            if previous is not None and not corroborated:
                status['conflicts'] += 1
                findings.append({'code': 'LOCAL_AI_CELL_CONFLICT', 'line': i+1, 'field': key,
                                 'retained': previous, 'alternative': value,
                                 **({'reason': 'moderate_proposal_not_verified'} if not strong_proposal else {}),
                                 **({'description_isolation': 'band_unavailable' if not band else
                                     'isolated_candidate' if mixed and reread else 'not_isolated'} if key == 'description' else {}),
                                 'requires_review': True})
                continue
            row[key] = value
            row.setdefault('evidence', {})[key] = deepcopy(parts)
            row.setdefault('_cell_candidates', {}).setdefault(key, []).append({'value': value, 'parts': deepcopy(parts), 'read': 'paddle-local'})
            changes.append((key, previous, value))
        numeric_keys = {'quantity', 'unit_price', 'amount'}
        numeric_changes = [change for change in changes if change[0] in numeric_keys]
        if numeric_changes and arithmetic_checks({}, [row]):
            # Reject inconsistent numeric corrections as a group. A verified
            # spelling or unit is independent of q * price = amount and should
            # not be discarded because an existing numeric issue remains.
            for key, _, _ in numeric_changes:
                if key in before:
                    row[key] = before[key]
                else:
                    row.pop(key, None)
                for store in ('evidence', '_cell_candidates'):
                    if key in before.get(store, {}):
                        row.setdefault(store, {})[key] = deepcopy(before[store][key])
                    else:
                        row.get(store, {}).pop(key, None)
            status['conflicts'] += 1
            findings.append({'code': 'LOCAL_AI_ROW_ARITHMETIC_RETAINED', 'line': i+1,
                             'fields': [key for key, _, _ in numeric_changes], 'requires_review': True})
            changes = [change for change in changes if change[0] not in numeric_keys]
        for key, previous, value in changes:
            status['cells_filled' if previous is None else 'cells_corrected'] += 1
            findings.append({'code': 'LOCAL_AI_CELL_ADOPTED', 'line': i+1, 'field': key,
                             'before': previous, 'after': value, 'requires_review': True})
    # A partially missing table is different from a mismatched row. Recover a
    # local-only row only from an unoccupied physical band and an independent
    # Tesseract read of its printed cells; arithmetic is a gate, not a source.
    baseline_count = len(result)
    recovered = []
    if (raster is not None and tuple(local_read.size) == raster.size and header
            and local_read.transform.get('coordinate_space') == 'V4 processed raster pixels'
            and len(used) == baseline_count and len(alternative) > baseline_count
            and all(matches[i][0] < matches[i+1][0] for i in range(baseline_count-1))
            and all(a is not None for a in [*lhs, *rhs])
            and all(a[0] < b[0] for a,b in zip(lhs, lhs[1:]))
            and all(a[0] < b[0] for a,b in zip(rhs, rhs[1:]))):
        from . import refine_v8 as refine
        from .table_v3 import STOP, METADATA, CONTINUED
        from decimal import Decimal
        required = ('description', 'quantity', 'unit_price', 'amount')
        keys = (*required, 'unit')
        width, height = raster.size
        # Require a real labelled header in both engines. No inherited-only
        # or unbounded receipt/footer recovery in this conservative path.
        primary_headers = [(read, grid.header_for(read)) for read in primary_reads
                           if read.boxes and tuple(read.size) == raster.size
                           and read.transform.get('coordinate_space') == 'V4 processed raster pixels']
        primary_headers = [(read, head) for read,head in primary_headers
                           if head and set(required).issubset(head.centers)]
        if (set(required).issubset(header.centers) and primary_headers
                and all(abs(head.centers[key]-header.centers[key])*width <= max(3, 1.5*h)
                        for _,head in primary_headers for key in required)
                and all(abs(head.bottom-header.bottom) <= 3*h for _,head in primary_headers)):
            top = max(header.bottom, *(head.bottom for _,head in primary_headers))
            footer = min(refine.safe_zone(local_read, header)['footer_start'],
                         *(refine.safe_zone(read, head)['footer_start'] for read,head in primary_headers))
            local_boxes = {(box.text, box.polygon) for box in local_read.boxes}
            heads = [header, *(head for _,head in primary_headers)]
            # Share the existing page verification budget; at most two missing
            # row rereads per page. Unknown column boundaries remain reviewable.
            attempts = 0
            for j, candidate in enumerate(alternative):
                if j in used or verification_budget <= 0 or attempts >= 2:
                    continue
                y, rh = rhs[j]
                # Only recover an interior gap bounded by two already linked
                # rows. Edge rows and continuation-only pages need more evidence.
                before_y = max((a[0] for a in lhs if a[0] < y), default=None)
                after_y = min((a[0] for a in lhs if a[0] > y), default=None)
                if (before_y is None or after_y is None or not top < y < footer
                        or any(abs(a[0]-y) <= max(3, h, rh, a[1]) for a in lhs)
                        or any(n != j and abs(a[0]-y) <= max(3, h, rh, a[1])
                               for n,a in enumerate(rhs))):
                    continue
                if not strong_row(candidate) or any(candidate.get(key) is None for key in required):
                    continue
                if (not all(Decimal(str(candidate[key])).is_finite() and Decimal(str(candidate[key])) > 0
                            for key in required[1:]) or arithmetic_checks({}, [candidate])):
                    continue
                label = v4.plain(candidate['description'])
                if (STOP.match(label) or METADATA.match(label) or CONTINUED.match(label)
                        or refine.financial_heading(candidate['description']) or not any(c.isalpha() for c in label)):
                    continue
                evidence = candidate.get('evidence', {})
                # Do not silently discard an extra populated financial cell.
                if any(candidate.get(key) is not None for key in ('vat_rate', 'vat_amount', 'discount', 'discount_amount')):
                    continue
                present = [key for key in keys if candidate.get(key) is not None]
                def in_column(part, key):
                    polygon = part.get('polygon', [])
                    return (bool(polygon) and all(key in head.centers and
                            all(column_index(head, x, width) == key for x,_ in polygon) for head in heads))
                if not all(_parts_strong(evidence.get(key, [])) and
                           all((part['text'], tuple(map(tuple, part['polygon']))) in local_boxes
                               and in_column(part, key) for part in evidence[key]) for key in present):
                    continue
                points = [point for key in present for part in evidence[key] for point in part['polygon']]
                low = max(top, (before_y+y)/2,
                          max(((a[0]+y)/2 for n,a in enumerate(rhs) if n != j and a[0] < y), default=top))
                high = min(footer, (after_y+y)/2,
                           min(((a[0]+y)/2 for n,a in enumerate(rhs) if n != j and a[0] > y), default=footer))
                if (not all(0 <= x <= width and low <= yy <= high for x,yy in points)
                        or max(yy for _,yy in points)-min(yy for _,yy in points) > 2*max(h,rh)):
                    continue
                pad = max(2, .3*max(h,rh))
                bbox = (max(0, math.floor(min(x for x,_ in points)-pad)),
                        max(math.ceil(low), math.floor(min(yy for _,yy in points)-pad)),
                        min(width, math.ceil(max(x for x,_ in points)+pad)),
                        min(math.floor(high), math.ceil(max(yy for _,yy in points)+pad)))
                if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                    continue
                attempts += 1
                verification_budget -= 1
                try:
                    read = v5.ocr_region(raster, bbox, f'local-ai-missing-row-{j+1}', 'vie+eng', 7, line_height=True)
                    if not read.boxes or len(read.lines) != 1:
                        continue
                    cells = {}
                    for k, box in enumerate(read.boxes):
                        role = column_index(header, (box.word[0]+box.word[2])/2, width)
                        cells.setdefault(role, []).append(k)
                    observed = row_evidence(read.boxes, cells)
                    # Unknown or unexpected printed cells must not be ignored.
                    if set(cells) != set(present):
                        continue
                    verified = {}
                    for key in present:
                        parts = sorted(observed[key], key=lambda part: min(x for x,_ in part['polygon']))
                        if not _parts_strong(parts, .80) or not all(in_column(part, key) for part in parts):
                            break
                        text = ' '.join(part['text'] for part in parts).strip()
                        value = number(text, key) if key in required[1:] else text
                        if value is None or grid.cell_identity(key, value) != grid.cell_identity(key, candidate[key]):
                            break
                        verified[key] = {'value': value, 'parts': parts, 'read': read.tag,
                                         'crop': bbox, 'engine': 'tesseract'}
                    if len(verified) != len(present):
                        continue
                except (RuntimeError, ValueError, ArithmeticError, v5.old.pytesseract.TesseractError):
                    continue
                row = deepcopy(candidate)
                for key, observation in verified.items():
                    row.setdefault('_cell_candidates', {}).setdefault(key, []).append(observation)
                recovered.append((y, j, row))
                status['rows_recovered'] += 1
    if recovered:
        positioned = [(a[0], i, row) for i,(a,row) in enumerate(zip(lhs,result))]
        positioned += [(y, baseline_count+j, row) for y,j,row in recovered]
        positioned.sort(key=lambda entry: entry[0])
        # Existing local findings refer to baseline row positions.
        new_lines = {index: n for n,(_,index,_) in enumerate(positioned,1)}
        for note in findings:
            if isinstance(note.get('line'), int) and note['line']-1 in new_lines:
                note['line'] = new_lines[note['line']-1]
        result = [row for _,_,row in positioned]
        for _,j,row in recovered:
            findings.append({'code': 'LOCAL_AI_ROW_RECOVERED', 'line': new_lines[baseline_count+j],
                             'alternative_row': j+1, 'reason': 'independent printed cell agreement',
                             'requires_review': True})
    if len(used) + len(recovered) != len(alternative) or len(used) != baseline_count:
        status['conflicts'] += 1
        findings.append({'code': 'LOCAL_AI_ROW_LINK_UNCONFIRMED', 'baseline_rows': baseline_count,
                         'alternative_rows': len(alternative), 'matched_rows': len(used),
                         'recovered_rows': len(recovered), 'requires_review': True})
    return result, findings


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--prepare':
        prepare_models(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == '--prepare-table':
        prepare_table_models(sys.argv[2])
    elif len(sys.argv) == 4 and sys.argv[1] == '--table-worker':
        table_worker(sys.argv[2], int(sys.argv[3]))
    elif len(sys.argv) == 4 and sys.argv[1] == '--worker':
        worker(sys.argv[2], int(sys.argv[3]))
    elif len(sys.argv) == 4 and sys.argv[1] == '--serve':
        worker(sys.argv[2], int(sys.argv[3]), persistent=True)
    elif len(sys.argv) == 4 and sys.argv[1] == '--serve-table':
        table_worker(sys.argv[2], int(sys.argv[3]), persistent=True)
    else:
        raise SystemExit('Use --prepare/--prepare-table MODEL_DIR or --worker/--table-worker/--serve/--serve-table MODEL_DIR THREADS')
