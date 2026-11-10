"""Functional checks using synthetic images; no personal image files needed."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

import rhombenpixel as rp


class MosaicTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root/'source.png'
        arr = np.zeros((40, 60, 4), dtype=np.uint8)
        arr[:, :30] = [255, 0, 0, 255]
        arr[:, 30:] = [0, 0, 255, 255]
        Image.fromarray(arr).save(self.source)

    def run_cli(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return rp.main([str(self.source), *map(str, args)])

    def test_raster_formats_and_dimensions(self):
        for ext in ['png', 'jpg', 'webp', 'tiff', 'bmp']:
            with self.subTest(ext=ext):
                out = self.root/f'test.{ext}'
                self.assertEqual(self.run_cli('-o', out, '--width', 101, '--height', 79, '--side', 8), 0)
                with Image.open(out) as im:
                    self.assertEqual(im.size, (101, 79))
                    self.assertGreater(np.asarray(im).std(), 10)

    def test_vector_formats(self):
        out = self.root/'test.svg'
        self.assertEqual(self.run_cli('-o', out, '--width', 120, '--height', 80), 0)
        svg = ET.parse(out).getroot()
        self.assertIn('viewBox', svg.attrib)
        self.assertFalse(any(e.tag.endswith('image') for e in svg.iter()))
        pdf = self.root/'test.pdf'
        self.assertEqual(self.run_cli('-o', pdf), 0)
        self.assertTrue(pdf.read_bytes().startswith(b'%PDF'))

    def test_transparency_and_hidden_rgb(self):
        arr = np.zeros((40, 60, 4), dtype=np.uint8)
        arr[:, :, :3] = [0, 255, 0]  # hidden green must not contaminate red
        arr[10:30, 20:40] = [255, 0, 0, 255]
        Image.fromarray(arr).save(self.source)
        out = self.root/'alpha.png'
        self.assertEqual(self.run_cli('-o', out, '--side', 4, '--background', 'transparent', '--blur', 1), 0)
        with Image.open(out) as im:
            pixels = np.asarray(im)
        self.assertEqual(pixels[0, 0, 3], 0)
        self.assertGreater(pixels[20, 30, 0], 240)
        self.assertLess(pixels[20, 30, 1], 5)

    def test_rotated_grid_has_no_uncovered_pixels(self):
        Image.new('RGB', (60, 40), 'red').save(self.source)
        out = self.root/'rotated.png'
        self.assertEqual(self.run_cli('-o', out, '--side', 7, '--angle', 31,
                                     '--offset-x', -4, '--offset-y', 3, '--antialias', 1), 0)
        with Image.open(out) as im:
            pixels = np.asarray(im)
        self.assertTrue(np.all(pixels[:, :, 0] == 255))
        self.assertTrue(np.all(pixels[:, :, 1:3] == 0))

    def test_fit_modes(self):
        for fit in ['contain', 'cover', 'stretch']:
            out = self.root/f'{fit}.png'
            self.assertEqual(self.run_cli('-o', out, '--width', 100, '--height', 100,
                                         '--fit', fit, '--antialias', 1), 0)
            with Image.open(out) as im:
                pixel = im.convert('RGB').getpixel((50, 0))
            self.assertEqual(pixel == (255, 255, 255), fit == 'contain')

    def test_palette_reproducible_and_bounded(self):
        colors = np.column_stack([np.random.default_rng(0).random((30, 3)), np.ones(30)])
        a = rp.reduce_colors(colors, 4, seed=123)
        b = rp.reduce_colors(colors, 4, seed=123)
        np.testing.assert_allclose(a, b)
        self.assertLessEqual(len(np.unique(a[:, :3], axis=0)), 4)
        merged = rp.reduce_colors(colors, 4, merge_delta=1000)
        self.assertEqual(len(np.unique(merged[:, :3], axis=0)), 1)
        flat = np.array([[1., 0, 0, 1], [1., 0, 0, 1]])
        np.testing.assert_allclose(rp.reduce_colors(flat, 100), flat, atol=1e-5)

    def test_size_inference_and_output_folder(self):
        self.assertEqual(self.run_cli('--output-dir', self.root/'nested', '--height', 80), 0)
        with Image.open(self.root/'nested/source_mosaic.png') as im:
            self.assertEqual(im.size, (120, 80))

    def test_reject_invalid_requests_and_preserve_input(self):
        before = self.source.read_bytes()
        for args in [('--side', '0'), ('--width', '0'), ('--colors', '-1'),
                     ('--angle', 'nan'), ('--scale', '2', '--width', '100'),
                     ('-o', str(self.root/'out.png'), '--format', 'jpg'),
                     ('--merge-delta', '5'), ('-o', str(self.source), '--overwrite')]:
            with self.subTest(args=args), self.assertRaises(SystemExit) as error:
                self.run_cli(*args)
            self.assertEqual(error.exception.code, 2)
        self.assertEqual(before, self.source.read_bytes())

    def test_overwrite_is_explicit(self):
        out = self.root/'existing.png'
        out.write_bytes(b'keep this')
        with self.assertRaises(SystemExit):
            self.run_cli('-o', out)
        self.assertEqual(out.read_bytes(), b'keep this')
        self.assertEqual(self.run_cli('-o', out, '--overwrite'), 0)

    def test_transparent_input_with_palette(self):
        Image.new('RGBA', (60, 40), (0, 0, 0, 0)).save(self.source)
        out = self.root/'empty.png'
        self.assertEqual(self.run_cli('-o', out, '--colors', 8, '--background', 'transparent'), 0)
        with Image.open(out) as im:
            self.assertEqual(im.getchannel('A').getextrema(), (0, 0))


if __name__ == '__main__':
    unittest.main()
