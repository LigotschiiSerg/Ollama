"""Integration smoke test for the image-based ruled table fallback."""
from pathlib import Path
from django.test import SimpleTestCase
from documents.table_regions import ruled_regions


class RuledRegionTests(SimpleTestCase):
    def test_works_on_built_scan(self):
        try:
            import fitz
            import cv2  # noqa: F401
        except ImportError:
            self.skipTest('opencv or pymupdf missing')
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as folder:
            doc = fitz.open()
            page = doc.new_page(width=400, height=500)
            for x in (30, 170, 360):
                page.draw_line((x, 300), (x, 420))
            for y in (300, 340, 380, 420):
                page.draw_line((30, y), (360, y))
            path = Path(folder) / 'grid.pdf'
            doc.save(path)
            doc.close()
            with fitz.open(path) as pdf:
                regions = ruled_regions(pdf[0])
            self.assertTrue(regions)
            self.assertGreater(regions[0].y0, 270)
