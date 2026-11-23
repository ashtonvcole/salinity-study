"""plot_tracer.py

Post-process the VTX/ADIOS2 output of tracer_post.py: 2x2 still panels, MP4
videos, and GIFs of iota and c = iota / h. Reads the BP file with adios2
directly (one block per MPI rank, DG1 data stored as per-cell vertices).

Example
    python plot_tracer.py runs/9days_evap/tracer_test_2.bp \
        --outdir plots/9days_evap --outputs stills mp4 gif --every 3
"""


import adios2
import argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.colors
import matplotlib.pyplot as plt
import matplotlib.tri as mtri
from matplotlib.animation import FFMpegWriter, PillowWriter
import numpy as np
import os


def parse_args():
    p = argparse.ArgumentParser(
        description='Plot tracer_post.py output: stills, MP4s, and GIFs.')
    p.add_argument('bp', help='VTX/ADIOS2 output (.bp) from tracer_post.py.')
    p.add_argument('--outdir', default='.', help='Output directory.')
    p.add_argument('--tag', default=None,
        help='Suffix for output names (default: the .bp file stem).')
    p.add_argument('--fields', nargs='+', choices=['iota', 'c'],
        default=['iota', 'c'])
    p.add_argument('--outputs', nargs='+', choices=['stills', 'mp4', 'gif'],
        default=['stills', 'mp4'])

    g = p.add_argument_group('stills')
    g.add_argument('--still-day', type=float, default=8.0,
        help='Elapsed day of the first panel offset (default: %(default)s).')
    g.add_argument('--still-hours', type=float, nargs=4,
        default=[0.0, 6.0, 12.0, 18.0],
        help='Hours after --still-day for the four panels '
             '(default: %(default)s).')

    g = p.add_argument_group('animations')
    g.add_argument('--fps', type=int, default=12)
    g.add_argument('--every', type=int, default=1,
        help='Use every Nth stored step (default: %(default)s).')
    g.add_argument('--gif-dpi', type=int, default=80,
        help='GIF resolution; GIFs are large, so this is lower than the '
             'MP4 dpi of 120 (default: %(default)s).')

    g = p.add_argument_group('color scales')
    g.add_argument('--iota-vmax', type=float, default=None,
        help='Upper limit for iota (default: 99th percentile over the '
             'still snapshots).')
    g.add_argument('--c-center', type=float, default=1.0)
    g.add_argument('--c-range', type=float, nargs=2, default=[0.0, 2.0],
        metavar=('LO', 'HI'))
    return p.parse_args()


class TracerFile:
    """Reads fields from tracer_post.py output, stitching MPI blocks."""

    def __init__(self, path):
        self.f = adios2.FileReader(path)
        v = self.f.available_variables()
        self.n_steps = int(v['step']['AvailableStepsCount'])
        self.n_blocks = int(v['NumberOfNodes']['Shape'])
        self.times = self.f.read('step', step_selection=[0, self.n_steps])
        # The mesh is static: read the geometry and connectivity once
        xs, tris, off = [], [], 0
        for b in range(self.n_blocks):
            g = self.f.read('geometry', step_selection=[0, 1], block_id=b)
            ce = self.f.read('connectivity', step_selection=[0, 1],
                             block_id=b)
            xs.append(g[:, :2] / 1e3)  # km
            tris.append(ce[:, 1:4] + off)  # Column 0 is the vertex count
            off += len(g)
        self.x = np.vstack(xs)
        self.tris = np.vstack(tris)

    def read(self, name, k):
        return np.concatenate([
            self.f.read(name, step_selection=[k, 1], block_id=b)[:, 0]
            for b in range(self.n_blocks)])

    def index_of(self, t):
        k = int(np.argmin(np.abs(self.times - t)))
        if abs(self.times[k] - t) > 0.5 * np.median(np.diff(self.times)):
            raise ValueError(f't = {t} s is outside the stored times '
                             f'[{self.times[0]}, {self.times[-1]}]')
        return k


def time_label(t):
    h = t / 3600.0
    return f'day {int(h // 24)} {int(h % 24):02d}:00 (t = {h:.0f} h)'


def field_style(name, args, iota_vmax):
    if name == 'c':
        lo, hi = args.c_range
        return dict(cmap='RdBu_r', dry=True,
            norm=matplotlib.colors.TwoSlopeNorm(args.c_center, lo, hi),
            label='c  (red: c > 1, blue: c < 1; grey: dry)')
    return dict(cmap='viridis', dry=False,
        norm=matplotlib.colors.Normalize(0.0, iota_vmax),
        label='iota = c h  [m]')


def draw(ax, tf, name, style, k):
    """Draw field `name` at stored step k on ax. Returns the mappable."""
    v = tf.read(name, k)
    tri = mtri.Triangulation(tf.x[:, 0], tf.x[:, 1], tf.tris)
    if style['dry']:
        # c is set to 0 where h < h_min; mask cells touching a dry vertex
        tri.set_mask((tf.read('c', k)[tf.tris] == 0).any(axis=1))
    m = ax.tripcolor(tri, v, shading='gouraud', cmap=style['cmap'],
                     norm=style['norm'], rasterized=True)
    ax.set_facecolor('0.8')
    ax.set_aspect('equal')
    return m


def make_stills(tf, name, style, steps, path):
    fig, axs = plt.subplots(2, 2, figsize=(12, 7.2), sharex=True,
                            sharey=True, constrained_layout=True)
    for ax, k in zip(axs.flat, steps):
        m = draw(ax, tf, name, style, k)
        ax.set_title(time_label(tf.times[k]), fontsize=10)
    for ax in axs[:, 0]:
        ax.set_ylabel('y [km]')
    for ax in axs[-1]:
        ax.set_xlabel('x [km]')
    fig.colorbar(m, ax=axs, shrink=0.8, extend='both', label=style['label'])
    fig.savefig(path, dpi=130)
    plt.close(fig)


def make_animation(tf, name, style, frames, path, writer, dpi):
    fig, ax = plt.subplots(figsize=(8, 6.4), constrained_layout=True)
    with writer.saving(fig, path, dpi=dpi):
        for n, k in enumerate(frames):
            ax.clear()
            m = draw(ax, tf, name, style, k)
            if n == 0:
                fig.colorbar(m, ax=ax, extend='both', label=style['label'])
            ax.set_xlabel('x [km]')
            ax.set_ylabel('y [km]')
            ax.set_title(f'{name}: {time_label(tf.times[k])}')
            writer.grab_frame()
    plt.close(fig)


def main():
    args = parse_args()
    os.makedirs(args.outdir, exist_ok=True)
    tag = args.tag or os.path.splitext(os.path.basename(
        os.path.normpath(args.bp)))[0]
    tf = TracerFile(args.bp)
    print(f'{tf.n_steps} steps, {tf.n_blocks} blocks, '
          f't = {tf.times[0]:.0f}..{tf.times[-1]:.0f} s')

    still_steps = [tf.index_of(args.still_day * 86400.0 + h * 3600.0)
                   for h in args.still_hours]
    iota_vmax = args.iota_vmax
    if iota_vmax is None:
        iota_vmax = float(np.percentile(np.concatenate(
            [tf.read('iota', k) for k in still_steps]), 99))
    print(f'iota color limit: 0..{iota_vmax:.3g}')

    frames = range(0, tf.n_steps, args.every)
    for name in args.fields:
        style = field_style(name, args, iota_vmax)
        if 'stills' in args.outputs:
            path = os.path.join(args.outdir, f'{name}_day{args.still_day:g}_{tag}.png')
            make_stills(tf, name, style, still_steps, path)
            print('wrote', path)
        if 'mp4' in args.outputs:
            path = os.path.join(args.outdir, f'{name}_video_{tag}.mp4')
            w = FFMpegWriter(fps=args.fps, codec='libx264',
                extra_args=['-pix_fmt', 'yuv420p', '-crf', '20'])
            make_animation(tf, name, style, frames, path, w, dpi=120)
            print('wrote', path)
        if 'gif' in args.outputs:
            path = os.path.join(args.outdir, f'{name}_anim_{tag}.gif')
            w = PillowWriter(fps=args.fps)
            make_animation(tf, name, style, frames, path, w,
                           dpi=args.gif_dpi)
            print('wrote', path)


if __name__ == '__main__':
    main()
