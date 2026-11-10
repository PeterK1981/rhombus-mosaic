"""Rhombus mosaics from images; run with --help for the command-line interface."""
from __future__ import annotations

import argparse
from pathlib import Path
import math
import sys

import numpy as np
from PIL import Image, ImageOps
from scipy.ndimage import gaussian_filter
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.collections import PolyCollection
from matplotlib.colors import to_rgba
from matplotlib.path import Path as PolygonPath
from matplotlib.patches import Rectangle


FORMATS = {'png': 'PNG', 'jpg': 'JPEG', 'jpeg': 'JPEG', 'webp': 'WEBP',
           'tif': 'TIFF', 'tiff': 'TIFF', 'bmp': 'BMP', 'svg': 'SVG', 'pdf': 'PDF'}


def positive(value):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError('must be a finite number greater than zero')
    return value


def nonnegative(value):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError('must be a finite nonnegative number')
    return value


def positive_int(value):
    result = int(value)
    if result <= 0:
        raise argparse.ArgumentTypeError('must be a positive integer')
    return result


def color(value):
    try:
        return to_rgba('none' if value.lower() == 'transparent' else value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def read_image(path, max_size=None, blur=0):
    """Apply EXIF orientation; blur premultiplied RGBA to avoid dark alpha halos."""
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert('RGBA')
    if max_size:
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    rgba = np.asarray(image, dtype=float) / 255
    if blur:
        alpha = gaussian_filter(rgba[:, :, 3], blur)
        premultiplied = gaussian_filter(rgba[:, :, :3] * rgba[:, :, 3:4], (blur, blur, 0))
        rgba[:, :, :3] = np.divide(premultiplied, alpha[:, :, None],
                                  out=np.zeros_like(premultiplied), where=alpha[:, :, None] > 0)
        rgba[:, :, 3] = alpha
    return rgba


def polygon_color(rgba, vertices):
    height, width = rgba.shape[:2]
    x0, y0 = np.maximum(np.floor(vertices.min(axis=0)).astype(int), 0)
    x1, y1 = np.minimum(np.ceil(vertices.max(axis=0)).astype(int) + 1, [width, height])
    if x0 >= x1 or y0 >= y1:
        return None
    ys, xs = np.mgrid[y0:y1, x0:x1]
    points = np.column_stack([xs.ravel() + .5, ys.ravel() + .5])
    mask = PolygonPath(vertices).contains_points(points).reshape(y1-y0, x1-x0)
    pixels = rgba[y0:y1, x0:x1][mask]
    if not len(pixels) or pixels[:, 3].sum() == 0:
        return None
    rgb = np.average(pixels[:, :3], axis=0, weights=pixels[:, 3])
    # Weighted sums can exceed 1 by floating-point roundoff (e.g. 1 + 2e-16).
    return np.clip(np.r_[rgb, pixels[:, 3].mean()], 0, 1)


def make_mosaic(rgba, side=40, angle=0, offset=(0, 0)):
    """Partition each flat-top hexagon into three non-overlapping rhombi."""
    height, width = rgba.shape[:2]
    theta = np.deg2rad(angle)
    rotation = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    offset = np.asarray(offset)
    corners = np.array([[0, 0], [width, 0], [0, height], [width, height]])
    local = (corners - offset) @ rotation
    low, high = local.min(axis=0), local.max(axis=0)
    dx, dy = 1.5 * side, np.sqrt(3) * side
    angles = np.deg2rad(np.arange(0, 360, 60))
    hexagon = side * np.column_stack([np.cos(angles), np.sin(angles)])
    polygons, colors = [], []
    for col in range(math.floor(low[0]/dx)-1, math.ceil(high[0]/dx)+2):
        shift = dy/2 if col % 2 else 0
        for row in range(math.floor((low[1]-shift)/dy)-1, math.ceil((high[1]-shift)/dy)+2):
            center = np.array([col*dx, row*dy+shift])
            vertices = center + hexagon
            for a, b, c in [(0, 1, 2), (2, 3, 4), (4, 5, 0)]:
                polygon = np.array([center, vertices[a], vertices[b], vertices[c]]) @ rotation.T + offset
                mean = polygon_color(rgba, polygon)
                if mean is not None:
                    polygons.append(polygon)
                    colors.append(mean)
    return np.asarray(polygons), np.asarray(colors).reshape(-1, 4)


def reduce_colors(colors, count, merge_delta=0, seed=42):
    """Equal tile weights, deterministic K-Means in Lab; merge with updated centroids."""
    if not count or not len(colors):
        return colors.copy()
    from sklearn.cluster import KMeans
    from skimage.color import rgb2lab, lab2rgb
    from scipy.spatial.distance import cdist
    lab = rgb2lab(colors[None, :, :3])[0]
    count = min(count, len(np.unique(lab, axis=0)))
    model = KMeans(n_clusters=count, random_state=seed, n_init=10).fit(lab)
    labels, centers = model.labels_.copy(), model.cluster_centers_.copy()
    weights = np.bincount(labels, minlength=count).astype(float)
    active = list(range(count))
    while merge_delta and len(active) > 1:
        distances = cdist(centers[active], centers[active])
        np.fill_diagonal(distances, np.inf)
        a, b = np.unravel_index(distances.argmin(), distances.shape)
        if distances[a, b] >= merge_delta:
            break
        i, j = active[a], active[b]
        centers[i] = (centers[i]*weights[i] + centers[j]*weights[j])/(weights[i]+weights[j])
        weights[i] += weights[j]
        labels[labels == j] = i
        active.remove(j)
    result = colors.copy()
    result[:, :3] = np.clip(lab2rgb(centers[None, :, :])[0][labels], 0, 1)
    return result


def output_dimensions(source_width, source_height, width=None, height=None, scale=1):
    if width and height:
        return width, height
    if width:
        return width, max(1, round(width*source_height/source_width))
    if height:
        return max(1, round(height*source_width/source_height)), height
    return max(1, round(source_width*scale)), max(1, round(source_height*scale))


def render(polygons, colors, source_size, output_size, *, fit='contain', margin=0,
           background=(1, 1, 1, 1), edge_color=None, edge_width=0, dpi=100):
    width, height = output_size
    sw, sh = source_size
    figure = Figure(figsize=(width/dpi, height/dpi), dpi=dpi, facecolor=background)
    ax = figure.add_axes([0, 0, 1, 1])
    ax.set_axis_off()
    span_x, span_y = sw+2*margin, sh+2*margin
    if fit != 'stretch':
        factor = (max if fit == 'contain' else min)(span_x/width, span_y/height)
        span_x, span_y = factor*width, factor*height
    ax.set_xlim((sw-span_x)/2, (sw+span_x)/2)
    ax.set_ylim((sh+span_y)/2, (sh-span_y)/2)
    if len(polygons):
        collection = PolyCollection(polygons, facecolors=colors,
                                    edgecolors=edge_color if edge_color is not None else 'none',
                                    linewidths=edge_width, antialiaseds=False)
        ax.add_collection(collection)
        collection.set_clip_path(Rectangle((0, 0), sw, sh, transform=ax.transData))
    return figure


def save_output(figure, path, fmt, size, dpi, antialias, quality, lossless, background):
    if fmt in ('SVG', 'PDF'):
        figure.savefig(path, format=fmt.lower(), dpi=dpi, facecolor=figure.get_facecolor())
        return
    # Render above target resolution, then downsample once; exact requested pixel size.
    figure.set_dpi(dpi*antialias)
    canvas = FigureCanvasAgg(figure)
    canvas.draw()
    image = Image.fromarray(np.asarray(canvas.buffer_rgba()).copy())
    if image.size != size:
        image = image.resize(size, Image.Resampling.LANCZOS)
    if fmt in ('JPEG', 'BMP'):
        matte = tuple(round(v*255) for v in background[:3]) if background[3] else (255, 255, 255)
        flattened = Image.new('RGB', image.size, matte)
        flattened.paste(image, mask=image.getchannel('A'))
        image = flattened
    options = {'dpi': (dpi, dpi)} if fmt in ('PNG', 'JPEG', 'TIFF', 'BMP') else {}
    if fmt == 'JPEG':
        options.update(quality=quality, subsampling=0)
    if fmt == 'WEBP':
        options.update(quality=quality, lossless=lossless)
    image.save(path, format=fmt, **options)


def parser():
    p = argparse.ArgumentParser(description='Create a rhombus mosaic from an image.',
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument('input', type=Path, help='source image (first frame of animated images)')
    location = p.add_mutually_exclusive_group()
    location.add_argument('-o', '--output', type=Path, help='full destination filename')
    location.add_argument('--output-dir', type=Path, help='destination folder (automatic filename)')
    p.add_argument('--format', choices=sorted(FORMATS), help='output format; otherwise inferred from output suffix or PNG')
    p.add_argument('--side', type=positive, default=40, help='rhombus side length in working-image pixels')
    p.add_argument('--blur', type=nonnegative, default=0, help='Gaussian sigma in working-image pixels')
    p.add_argument('--angle', type=float, default=0, help='grid rotation in degrees')
    p.add_argument('--offset-x', type=float, default=0, help='horizontal grid offset in working-image pixels')
    p.add_argument('--offset-y', type=float, default=0, help='vertical grid offset in working-image pixels')
    p.add_argument('--colors', type=int, default=0, help='maximum palette size; 0 keeps per-tile averages')
    p.add_argument('--merge-delta', type=nonnegative, default=0, help='merge palette centers below this Lab Euclidean distance (Delta E 76)')
    p.add_argument('--seed', type=int, default=42, help='K-Means random seed')
    p.add_argument('--max-input-size', type=positive_int, help='resize input longest edge before analysis (optional performance limit)')
    p.add_argument('--width', type=positive_int, help='output width in pixels')
    p.add_argument('--height', type=positive_int, help='output height in pixels')
    p.add_argument('--scale', type=positive, help='output scale relative to working image; alternative to width/height')
    p.add_argument('--fit', choices=['contain', 'cover', 'stretch'], default='contain', help='fit when output aspect ratio differs')
    p.add_argument('--margin', type=nonnegative, default=0, help='canvas margin in working-image pixels before fitting')
    p.add_argument('--background', type=color, default=(1, 1, 1, 1), help='Matplotlib color or transparent; quote hex colors')
    p.add_argument('--edge-color', type=color, help='tile outline color; omitted means no outlines')
    p.add_argument('--edge-width', type=nonnegative, default=0, help='outline width in points (requires edge-color)')
    p.add_argument('--dpi', type=positive, default=100, help='raster DPI metadata and vector page size: pixels / DPI inches')
    p.add_argument('--antialias', type=positive_int, choices=range(1, 5), default=2, help='raster supersampling factor')
    p.add_argument('--quality', type=int, default=95, help='JPEG/WebP quality, 1–100')
    p.add_argument('--lossless', action='store_true', help='lossless WebP output')
    p.add_argument('--overwrite', action='store_true', help='allow replacing an existing output (never the input)')
    return p


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    if args.colors < 0 or not 1 <= args.quality <= 100 or not 0 <= args.seed <= 2**32-1:
        p.error('colors must be >= 0, quality 1–100, and seed 0–4294967295')
    if not all(math.isfinite(v) for v in (args.angle, args.offset_x, args.offset_y)):
        p.error('angle and offsets must be finite')
    if args.scale is not None and (args.width or args.height):
        p.error('--scale cannot be combined with --width/--height')
    if args.merge_delta and not args.colors:
        p.error('--merge-delta requires --colors > 0')
    if args.edge_width and args.edge_color is None:
        p.error('--edge-width requires --edge-color')
    suffix = args.output.suffix.lower().lstrip('.') if args.output else ''
    extension = args.format or suffix or 'png'
    if extension not in FORMATS:
        p.error(f'unsupported output format: {extension}')
    fmt = FORMATS[extension]
    if args.format and suffix and FORMATS.get(suffix) != fmt:
        p.error('--format and output filename extension must agree')
    if args.lossless and fmt != 'WEBP':
        p.error('--lossless is only available for WebP')
    destination = args.output or (args.output_dir or args.input.parent) / f'{args.input.stem}_mosaic.{extension}'
    if not destination.suffix:
        destination = destination.with_suffix('.'+extension)
    if destination.resolve() == args.input.resolve():
        p.error('input and output must be different files')
    if destination.exists() and not args.overwrite:
        p.error(f'output exists: {destination}; use --overwrite to replace it')
    try:
        rgba = read_image(args.input, args.max_input_size, args.blur)
        height, width = rgba.shape[:2]
        size = output_dimensions(width+2*args.margin, height+2*args.margin,
                                 args.width, args.height, args.scale or 1)
        polygons, colors = make_mosaic(rgba, args.side, args.angle, (args.offset_x, args.offset_y))
        colors = reduce_colors(colors, args.colors, args.merge_delta, args.seed)
        figure = render(polygons, colors, (width, height), size, fit=args.fit, margin=args.margin,
                        background=args.background, edge_color=args.edge_color,
                        edge_width=args.edge_width, dpi=args.dpi)
        destination.parent.mkdir(parents=True, exist_ok=True)
        save_output(figure, destination, fmt, size, args.dpi, args.antialias,
                    args.quality, args.lossless, args.background)
        print(f'Saved {destination.resolve()} | {size[0]} x {size[1]} | {fmt} | {len(colors)} tiles')
        return 0
    except (OSError, ValueError, ImportError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
