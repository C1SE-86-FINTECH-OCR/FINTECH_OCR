"""Alternative paper views only; preserves original bytes and coordinates."""
from PIL import ImageOps,ImageFilter
from . import pipeline_v5 as v5

def views(image):
    image=ImageOps.exif_transpose(image).convert('RGB')
    if image.width*image.height>30_000_000:raise ValueError('V8 image exceeds 30MP')
    paper,transform=v5.paper_view(image)
    gray=ImageOps.autocontrast(paper.convert('L'),cutoff=.15)
    # No binarization/erosion: retain Vietnamese accents and monetary marks.
    enhanced=gray.filter(ImageFilter.UnsharpMask(radius=.8,percent=80,threshold=5)) if transform['method']!='original' else None
    try:
        yield gray,{**transform,'variant':'paper-gray','filters':'mild autocontrast, no erosion'}
        if enhanced is not None:yield enhanced,{**transform,'variant':'paper-mild-sharp','filters':'mild unsharp; alternative, not replacement'}
    finally:
        gray.close()
        if enhanced is not None:enhanced.close()
        if paper is not image:paper.close()
        image.close()
