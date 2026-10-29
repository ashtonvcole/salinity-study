import argparse
import math
import numpy as np
import matplotlib.pyplot as plt
from owi_util import parse_owi_date, read_owi_header, read_owi_data

def load_owi(path: str) -> tuple[str, list[dict]]:
    """Read every record of an OWI file.

    Records may each have their own grid. A record holds one field (e.g.
    pressure, precipitation) or more (e.g. wind u and v), which is detected from
    the amount of data in the record.

    Arguments
        path (str): A path to an OWI file.

    Returns
        tuple[str, list[dict]]:
            - title (str): The descriptive title from the first line.
            - records (list[dict]): The records in file order. Each has keys
              "date" (datetime.datetime), "lats" and "lons" (np.ndarray, grid
              coordinates of length ilat and ilon), and "data" (np.ndarray, of
              dimension (num_fields, ilat, ilon)).
    """
    records = []
    with open(path) as f:
        title, _, _ = read_owi_header(f)
        while (record := read_owi_data(f)) is not None:
            ilat, ilon, dx, dy, swlat, swlon, date, data = record
            records.append({
                'date': date,
                'lats': swlat + dy * np.arange(ilat),
                'lons': swlon + dx * np.arange(ilon),
                'data': data.reshape(-1, ilat, ilon),
            })
    if not records:
        raise ValueError(f'No records found in {path}.')
    return title, records

def select_records(records: list[dict], indices: list[int] | None,
    times: list[str] | None) -> list[int]:
    """Choose records by position and/or by date.

    Arguments
        records (list[dict]): The records from load_owi.
        indices (list[int] | None): Positions in the file. Negative values
            count from the end.
        times (list[str] | None): Dates as YYYYMMDDHH or YYYYMMDDHHMM.

    Returns
        list[int]: Unique non-negative positions, in the order requested. If
            neither indices nor times is given, the first record.
    """
    chosen = []
    for i in indices or []:
        if not -len(records) <= i < len(records):
            raise ValueError(f'Index {i} is out of range for {len(records)} records.')
        chosen.append(i % len(records))
    for text in times or []:
        date = parse_owi_date(text)
        matches = [i for i, record in enumerate(records) if record['date'] == date]
        if not matches:
            raise ValueError(f'No record with date {date}.')
        chosen += matches
    if not chosen:
        chosen = [0]
    # Remove duplicates, keeping order
    return list(dict.fromkeys(chosen))

def plot_records(title: str, records: list[dict], chosen: list[int],
    ncols: int | None = None, cmap: str = 'viridis', vmin: float | None = None,
    vmax: float | None = None, label: str = '') -> plt.Figure:
    """Plot selected records, one panel per record and field.

    All panels share a single color scale so that they can be compared.

    Arguments
        title (str): The figure title.
        records (list[dict]): The records from load_owi.
        chosen (list[int]): Positions of the records to plot.
        ncols (int | None): Number of panel columns. Default is the number of
            fields per record for multi-field files, otherwise up to 3.
        cmap (str): A matplotlib colormap name.
        vmin (float | None): The lower color limit. Default is the data minimum.
        vmax (float | None): The upper color limit. Default is the data maximum.
        label (str): A label for the colorbar, e.g. the quantity and units.

    Returns
        matplotlib.figure.Figure: The figure.
    """
    # One panel for each (record, field) pair
    panels = [(i, j) for i in chosen for j in range(records[i]['data'].shape[0])]
    max_fields = max(records[i]['data'].shape[0] for i in chosen)
    if ncols is None:
        ncols = max_fields if max_fields > 1 else min(len(panels), 3)
    nrows = math.ceil(len(panels) / ncols)

    # Shared color limits
    if vmin is None:
        vmin = min(np.nanmin(records[i]['data'][j]) for i, j in panels)
    if vmax is None:
        vmax = max(np.nanmax(records[i]['data'][j]) for i, j in panels)

    fig, axes = plt.subplots(nrows, ncols, figsize=(4.5 * ncols + 1.5, 4.0 * nrows),
        squeeze=False, constrained_layout=True)
    mesh = None
    for ax, (i, j) in zip(axes.ravel(), panels):
        record = records[i]
        # Nodes are treated as cell centers
        mesh = ax.pcolormesh(record['lons'], record['lats'], record['data'][j],
            cmap=cmap, vmin=vmin, vmax=vmax, shading='nearest')
        name = f'[{i}] {record['date']:%Y-%m-%d %H:%M}'
        if record['data'].shape[0] > 1:
            name += f' (field {j + 1})'
        ax.set_title(name)
        ax.set_xlabel('Longitude (deg)')
        ax.set_ylabel('Latitude (deg)')
        ax.set_aspect('equal')
    # Hide unused panels
    for ax in axes.ravel()[len(panels):]:
        ax.set_visible(False)
    fig.colorbar(mesh, ax=axes, label=label)
    fig.suptitle(title)
    return fig

def main():
    parser = argparse.ArgumentParser(description='A script to plot records from an OWI file.')
    parser.add_argument('input', help='Input OWI file, e.g. fort.425.')
    parser.add_argument('--index', nargs='+', type=int, metavar='I',
        help='Positions of records to plot, starting at 0. Negative values count from the end (default: 0).')
    parser.add_argument('--time', nargs='+', metavar='YYYYMMDDHH[MM]',
        help='Dates of records to plot. May be combined with --index.')
    parser.add_argument('--list', action='store_true',
        help='List the records in the file instead of plotting.')
    parser.add_argument('--output', help='Save the figure to this path instead of showing it.')
    parser.add_argument('--label', default='', help='Colorbar label, e.g. "Evaporation (m/s)".')
    parser.add_argument('--cmap', default='viridis', help='Matplotlib colormap name (default: viridis).')
    parser.add_argument('--vmin', type=float, help='Lower color limit (default: data minimum).')
    parser.add_argument('--vmax', type=float, help='Upper color limit (default: data maximum).')
    parser.add_argument('--ncols', type=int, help='Number of panel columns.')
    args = parser.parse_args()

    title, records = load_owi(args.input)

    if args.list:
        print(title)
        for i, record in enumerate(records):
            print(
                f'[{i}] {record['date']:%Y-%m-%d %H:%M} '
                f'{record['data'].shape[0]} field(s), '
                f'{record['lats'].size} x {record['lons'].size} nodes, '
                f'lat [{record['lats'][0]:.3f}, {record['lats'][-1]:.3f}], '
                f'lon [{record['lons'][0]:.3f}, {record['lons'][-1]:.3f}]'
            )
        return

    chosen = select_records(records, args.index, args.time)
    fig = plot_records(title, records, chosen, args.ncols, args.cmap, args.vmin, args.vmax, args.label)
    if args.output:
        fig.savefig(args.output, dpi=130)
    else:
        plt.show()

if __name__ == '__main__':
    main()
