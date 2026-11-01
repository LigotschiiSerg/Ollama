"""Find ruled table regions on scanned pages; geometry only, no OCR.

Optional OpenCV helper: not all tables have rules, so this is a fallback,
not a substitute for Docling/TableFormer.
"""
import fitz


def ruled_regions(page, scale=1.3):
    try:
        import cv2
        import numpy as np
    except ImportError:
        return []
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csGRAY, alpha=False)
    image = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
    dark = cv2.threshold(image, 185, 255, cv2.THRESH_BINARY_INV)[1]
    horizontal = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(
        cv2.MORPH_RECT, (max(24, int(pix.width * .09)), 1)))
    vertical = cv2.morphologyEx(dark, cv2.MORPH_OPEN, cv2.getStructuringElement(
        cv2.MORPH_RECT, (1, max(24, int(pix.height * .035)))))
    outlines, _ = cv2.findContours(cv2.add(horizontal, vertical), cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    found = []
    for outline in outlines:
        x, y, w, h = cv2.boundingRect(outline)
        if w < pix.width * .42 or h < 35 or (w * h) < pix.width * pix.height * .01:
            continue
        # Minimum two horizontal strokes, to avoid treating underlined text as a table.
        lines = cv2.reduce(horizontal[y:y+h, x:x+w], 1, cv2.REDUCE_MAX).reshape(-1)
        bands = int(bool(lines[0])) + sum(1 for i in range(1, len(lines)) if lines[i] and not lines[i-1])
        if bands < 2:
            continue
        margin = 5
        rect = fitz.Rect(max(0, (x-margin)/scale), max(0, (y-margin)/scale),
                         min(page.rect.width, (x+w+margin)/scale),
                         min(page.rect.height, (y+h+margin)/scale))
        found.append(rect)
    # Bigger region takes precedence over nested ones.
    return sorted(found, key=lambda r: (r.y0, r.x0))
