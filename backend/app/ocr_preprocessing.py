"""OpenCV preprocessing with unchanged source bytes and a Pillow fallback."""
from contextlib import contextmanager
from contextvars import ContextVar
from math import atan2, degrees
from statistics import median


_observations = ContextVar('ocr_preprocessing_observations', default=None)


def normalize_image(image):
    """Composite transparent document pixels on paper white before grayscale."""
    from PIL import Image, ImageOps
    image = ImageOps.exif_transpose(image)
    if 'A' in image.getbands() or 'transparency' in image.info:
        rgba = image.convert('RGBA')
        paper = Image.new('RGBA', rgba.size, (255, 255, 255, 255))
        image = Image.alpha_composite(paper, rgba)
    return image.convert('RGB')


@contextmanager
def capture_preprocessing():
    observations = []
    token = _observations.set(observations)
    try:
        yield observations
    finally:
        _observations.reset(token)


def preprocess(image):
    result, observation = _preprocess(image)
    observations = _observations.get()
    if observations is not None:
        observations.append(observation)
    return result, observation


def _preprocess(image):
    from PIL import Image, ImageOps

    if image.width * image.height > 30_000_000:
        raise ValueError('Image exceeds OCR pixel limit')
    image = normalize_image(image)
    try:
        import cv2
        import numpy as np
    except (ImportError, OSError) as exc:
        return image, {'engine': 'pillow', 'opencv_status': 'unavailable',
                       'error_type': type(exc).__name__}
    try:
        gray = np.asarray(ImageOps.exif_transpose(image).convert('L'))
        height, width = gray.shape
        # Technical image bounds, unrelated to the confidence policy TBD-02.
        low, high = np.percentile(gray, (5, 95))
        contrast = high - low < 100
        prepared = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray) if contrast else gray
        ratio = min(1.0, 1000 / max(width, height))
        proxy = cv2.resize(prepared, (max(1, round(width * ratio)), max(1, round(height * ratio))))
        edges = cv2.Canny(proxy, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=40,
                                minLineLength=max(30, proxy.shape[1] // 5), maxLineGap=12)
        angles = []
        if lines is not None:
            for x0, y0, x1, y1 in lines[:, 0]:
                angle = degrees(atan2(float(y1 - y0), float(x1 - x0)))
                angle = (angle + 90) % 180 - 90
                if abs(angle) <= 5:
                    angles.append(angle)
        angle = median(angles) if len(angles) >= 3 else 0.0
        agreement = angles and median(abs(value - angle) for value in angles) <= .5
        rotated = bool(agreement and .2 <= abs(angle) <= 5)
        if rotated:
            # Expand the canvas to preserve edges of the original document.
            matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
            cosine, sine = abs(matrix[0, 0]), abs(matrix[0, 1])
            out_width = int(height * sine + width * cosine + 1)
            out_height = int(height * cosine + width * sine + 1)
            if out_width * out_height <= 30_000_000:
                matrix[0, 2] += out_width / 2 - width / 2
                matrix[1, 2] += out_height / 2 - height / 2
                prepared = cv2.warpAffine(prepared, matrix, (out_width, out_height),
                                         flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT,
                                         borderValue=255)
            else:
                rotated = False
        return Image.fromarray(prepared).convert(image.mode), {
            'engine': 'opencv', 'opencv_status': 'applied', 'opencv_version': cv2.__version__,
            'contrast_enhanced': bool(contrast), 'rotation_degrees': float(angle) if rotated else 0.0,
            'coordinate_space': 'OpenCV prepared raster pixels',
        }
    except Exception as exc:
        return image, {'engine': 'pillow', 'opencv_status': 'failed',
                       'error_type': type(exc).__name__}


@contextmanager
def hybrid_preprocessing():
    """Scope the hook under the existing raster lock, before OCR/box capture."""
    from tools.ocr_benchmark import pipeline_v4
    from tools.ocr_benchmark.profiling import _lock

    observations = []
    with _lock:
        original = pipeline_v4.prepare

        def prepare(image):
            # OpenCV operates before the existing sizing/orientation stages.
            # All downstream boxes/crops therefore refer to the final raster.
            prepared, observation = preprocess(image)
            raster, info = original(prepared)
            observations.append(observation)
            return raster, {**info, 'opencv': observation}

        pipeline_v4.prepare = prepare
        try:
            yield observations
        finally:
            pipeline_v4.prepare = original
