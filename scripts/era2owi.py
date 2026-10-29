import argparse
import sys
import numpy as np
from owi_util import write_owi_header, write_owi_data
from grib_util import read_era5

def main():
    parser = argparse.ArgumentParser(description='A script to convert ERA data to OWI format.')
    parser.add_argument('input', help='Input GRIB file.')
    parser.add_argument('output', help='Output OWI file, e.g. fort.425.')
    parser.add_argument('--title', required=True, help='Descriptive title for the first line (55 characters max).')
    parser.add_argument('--bbox', nargs=4, type=float, metavar=('WEST', 'SOUTH', 'EAST', 'NORTH'),
        help='Rectangle to extract, in degrees. Nodes on the boundary are included. Default: the whole grid.')
    parser.add_argument('--stride', type=int, default=1,
        help='Keep every Nth grid line in both directions, e.g. 4 for a coarse basin file (default: 1).')
    parser.add_argument('--coarsen', choices=['sample', 'mean'], default='sample',
        help='How to reduce resolution when --stride > 1: pick every Nth node, or average NxN blocks (default: sample).')
    parser.add_argument('--accum-to-rate', action='store_true',
        help='Divide accumulated fields by their accumulation period, giving a rate per second.')
    parser.add_argument('--scale', type=float, default=1.0,
        help='Factor multiplied into the data after any rate conversion, e.g. 3.6e6 for m/s to mm/hr (default: 1).')
    parser.add_argument('--negate', action='store_true',
        help='Flip the sign. ERA5 reports evaporation as negative (downward-positive convention).')
    args = parser.parse_args()

    if args.stride < 1:
        parser.error('--stride must be a positive integer.')
    if len(args.title) > 55:
        parser.error('--title must be at most 55 characters.')
    if args.bbox is not None and (args.bbox[0] >= args.bbox[2] or args.bbox[1] >= args.bbox[3]):
        parser.error('--bbox requires WEST < EAST and SOUTH < NORTH.')

    lat, lon, records = read_era5(args.input, args.bbox, args.stride, args.coarsen, args.accum_to_rate, args.negate)
    if args.scale != 1.0:
        records = [(date, data * args.scale) for date, data in records]
    # Grid spacing is uniform by construction, but single-node axes have none.
    dy = lat[1] - lat[0] if lat.size > 1 else 0.0
    dx = lon[1] - lon[0] if lon.size > 1 else 0.0

    with open(args.output, 'w') as f:
        write_owi_header(
            f=f,
            title=args.title,
            start_date=records[0][0],
            end_date=records[-1][0]
        )
        for date, data in records:
            write_owi_data(
                f=f,
                ilat=lat.size,
                ilon=lon.size,
                dx=dx,
                dy=dy,
                swlat=lat[0],
                swlon=lon[0],
                date=date,
                data=data.ravel()
            )
    print(
        f'Wrote {len(records)} records, {lat.size} x {lon.size} nodes, '
        f'lat [{lat[0]:.3f}, {lat[-1]:.3f}], lon [{lon[0]:.3f}, {lon[-1]:.3f}], '
        f'dx={dx:.3f}, dy={dy:.3f} to {args.output}',
        file=sys.stderr
    )

if __name__ == '__main__':
    main()
