import datetime as dt
import eccodes
import numpy as np

# Tolerance in degrees for comparing grid coordinates to the bounding box.
EPS = 1e-6
# Fixed-length units from ecCodes' stepUnits.table; M, Y, 10Y, 30Y, C are variable-length
STEP_SECONDS = {'s': 1, 'm': 60, 'h': 3600, 'D': 86400,
                '15m': 900, '30m': 1800, '3h': 10800, '6h': 21600, '12h': 43200}

def read_grib_grid(h: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read lon/lat grid data from a GRIB message in order of ascending
    longitude and latitude.

    Arguments
        h (int): The grib message ID number.
    
    Returns
        tuple[np.ndarray, np.ndarray, np.ndarray]:
            - lats (np.ndarray): A list of the grid latitudes, of length num_lats.
            - lons (np.ndarray): A list of the grid longitudes, of length num_lons.
            - values (np.ndarray): An array of grid data, of dimension
              (num_lats, num_lons).
    """

    # Check that the message is a regular lon/lat grid
    if eccodes.codes_get(h, 'gridType') != 'regular_ll':
        raise ValueError('Only regular_ll GRIB grids are supported.')

    # Check that the message is row-major
    if eccodes.codes_get(h, 'jPointsAreConsecutive'):
        raise ValueError('Column-major GRIB scanning is not supported.')

    # Get grid dimensions
    ni = eccodes.codes_get(h, 'Ni') # Number of longitude meridians
    nj = eccodes.codes_get(h, 'Nj') # Number of latitude parallels
    lat0 = eccodes.codes_get(h, 'latitudeOfFirstGridPointInDegrees')
    lon0 = eccodes.codes_get(h, 'longitudeOfFirstGridPointInDegrees')
    dlat = eccodes.codes_get(h, 'jDirectionIncrementInDegrees')
    dlon = eccodes.codes_get(h, 'iDirectionIncrementInDegrees')

    # Adjust sign of grid spacing based on how the grid data is ordered
    if not eccodes.codes_get(h, 'jScansPositively'):
        dlat = -dlat
    if eccodes.codes_get(h, 'iScansNegatively'):
        dlon = -dlon

    # Create lists of longitudes and latitudes
    lats = lat0 + dlat * np.arange(nj)
    lons = lon0 + dlon * np.arange(ni)

    # Get grid values and reshape
    # The grid is stored in row-major order
    # Row = fixed latitude parallel, index is j
    # column = fixed longitude meridian, index is i
    # Resulting array is nj rows by ni columns
    # Set missing values to NaN
    eccodes.codes_set(h, 'missingValue', 1e30)
    values = eccodes.codes_get_values(h).reshape(nj, ni)
    values[values > 1e29] = np.nan

    # Reorder the data to go from southwest to northeast
    # i.e., values[0, 0] is the southwest corner
    ilats = np.argsort(lats) # Ordering of indices that gives increasing lats
    ilons = np.argsort(lons) # Ordering of indices that gives increasing lons
    return lats[ilats], lons[ilons], values[np.ix_(ilats, ilons)]

def select_bbox(lats: np.ndarray, lons: np.ndarray, data: np.ndarray,
    bbox: tuple[float, float, float, float]) -> tuple[np.ndarray, np.ndarray,
    np.ndarray]:
    """Crop lon/lat grid data to a rectangle.

    Grid longitudes are re-expressed in the 360 degree window starting at the
    western bound, so a 0-360 file and a -180-180 bbox (or vice versa) agree.

    Arguments
        lats (np.ndarray): A list of the grid latitudes, of length num_lats.
        lons (float): A list of the grid longitudes, of length num_lons.
        data (np.ndarray): An array of grid data, of dimension (num_lats, num_lons).
        bbox (tuple[float, float, float, float]): A cropping box specified by
            (west, south, east, north).

    Returns
        tuple[float, float, np.ndarray]: A new cropped subgrid.
            - lats (np.ndarray): A list of the grid latitudes, of new length num_lats.
            - lons (np.ndarray): A list of the grid longitudes, of new length num_lons.
            - values (np.ndarray): An array of grid data, of new dimension
              (num_lats, num_lons).
    """
    west, south, east, north = bbox

    # Re-express longitudes in same period as west
    # Sort in increasing order
    lons = west + (lons - west) % 360.0
    ilons = np.argsort(lons)
    lons = lons[ilons]
    data = data[:, ilons]

    # Create boolean masks to extract subgrid
    mlats = (lats >= south - EPS) & (lats <= north + EPS)
    mlons = (lons >= west - EPS) & (lons <= east + EPS)
    if not mlats.any() or not mlons.any():
        raise ValueError('Bounding box contains no grid nodes.')
    return lats[mlats], lons[mlons], data[np.ix_(mlats, mlons)]

def coarsen(lats: np.ndarray, lons: np.ndarray, data: np.ndarray,
    stride: int, method: str) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Keep every stride-th grid line, by sampling or by block averaging.

    Block averaging uses non-overlapping stride x stride blocks anchored at the
    southwest corner and drops incomplete blocks at the north and east edges.
    The coarse node is placed at the block centroid.

    Arguments
        lats (np.ndarray): A list of the grid latitudes, of length num_lats.
        lons (float): A list of the grid longitudes, of length num_lons.
        data (np.ndarray): An array of grid data, of dimension (num_lats, num_lons).
        stride (int): Grid spacing to retain.
        method (str): How to compute new grid values.
            - "sample": data is sampled in-place.
            - "mean": data is averaged from neighboring points.

    Returns
        tuple[np.ndarray, np.ndarray, np.ndarray]: A new cropped subgrid.
            - lats (np.ndarray): A list of the grid latitudes, of new length
              num_lats.
            - lons (np.ndarray): A list of the grid longitudes, of new length
              num_lons.
            - values (np.ndarray): An array of grid data, of new dimension
              (num_lats, num_lons).
    """

    # Validate method
    if method not in ('sample', 'mean'):
        raise ValueError(f"Unknown coarsening method '{method}'.")

    # Case: no stride
    if stride == 1:
        return lats, lons, data
    
    # Case: sampling, easy with array slicing
    if method == 'sample':
        return lats[::stride], lons[::stride], data[::stride, ::stride]

    # Case: averaging
    # Use reshape to create a third axis to average along
    nlats = (lats.size // stride) * stride # Number used for averaging
    nlons = (lons.size // stride) * stride
    if nlats == 0 or nlons == 0:
        raise ValueError('Stride is larger than the extracted region.')
    blocks = data[:nlats, :nlons].reshape(nlats // stride, stride, nlons // stride, stride)
    return (
        lats[:nlats].reshape(-1, stride).mean(axis=1),
        lons[:nlons].reshape(-1, stride).mean(axis=1),
        blocks.mean(axis=(1, 3)),
    )

def read_era5(path: str, bbox: tuple[float, float, float, float], stride: int,
    method: str = 'sample', accum_to_rate: bool = False, negate: bool = False) -> tuple[
    np.ndarray, np.ndarray, dict[dt.datetime, np.ndarray]]:
    """Read an ERA5 GRIB file and extract time series grid data.
    
    Read all messages, returning the grid and a time-sorted list of
    (valid time, 2D field) pairs, with extraction and conversion applied.

    Arguments
        path (str): A path to an ERA5 GRIB file.
        bbox (tuple[float, float, float, float]): A cropping box specified by
            (west, south, east, north).
        stride (int): Grid spacing to retain.
        method (str): How to compute new strided grid values. Default is
            "sample".
            - "sample": data is sampled in-place.
            - "mean": data is averaged from neighboring points.
        accum_to_rate (bool): Whether to convert an accumulated value to a
            rate value per second.
        negate (bool): Whether to flip the sign of the data.
    
    Returns
        tuple[np.ndarray, np.ndarray, dict[dt.datetime, np.ndarray]]: A new
            cropped subgrid.
            - lats (np.ndarray): A list of the grid latitudes, of new length
                num_lats.
            - lons (np.ndarray): A list of the grid longitudes, of new length
                num_lons.
            - records (list[tuple[datetime, ndarray]]): A list of grid data
              records, consisting of a date-time and grid data.
    """
    records = {}
    name = None
    lats = None
    lons = None
    with open(path, 'rb') as f:
        # Read sequential messages (records) from the GRIB file
        # These are loaded into memory under the hood
        # The Python interface returns an ID h for data access calls
        while (h := eccodes.codes_grib_new_from_file(f)) is not None:
            try:
                short_name = eccodes.codes_get(h, 'shortName')
                if name not in (None, short_name):
                    raise ValueError(f'File contains multiple parameters: {name}, {short_name}.')
                name = short_name

                date = eccodes.codes_get(h, 'validityDate')
                time = eccodes.codes_get(h, 'validityTime')
                valid = dt.datetime.strptime(f'{date:08d}{time:04d}', '%Y%m%d%H%M')
                if valid in records:
                    raise ValueError(f'Duplicate valid time {valid}.')

                # Read the message (grid data)
                the_lats, the_lons, data = read_grib_grid(h)

                # If desired, filter to a bounding box
                if bbox is not None:
                    the_lats, the_lons, data = select_bbox(the_lats, the_lons, data, bbox)

                # If desired, apply a stride
                if stride > 1:
                    the_lats, the_lons, data = coarsen(the_lats, the_lons, data, stride, method)

                # Error checks
                if np.isnan(data).any():
                    raise ValueError(f'Missing values in extracted region at {valid}.')
                if lats is None:
                    lats = the_lats
                    lons = the_lons
                elif not (np.allclose(the_lats, lats) and np.allclose(the_lons, lons)):
                    raise ValueError('Grid changes between messages.')

                # If desired, convert an accumulated value to an average rate
                # For now, unit conversion is not supported
                # units_in = eccodes.codes_get(h, 'units')
                step_type = eccodes.codes_get(h, 'stepType')
                if accum_to_rate:
                    if step_type != 'accum':
                        raise ValueError(f"--accum-to-rate requested but stepType is '{step_type}'.")
                    unit = eccodes.codes_get_string(h, 'stepUnits')
                    if unit not in STEP_SECONDS:
                        raise ValueError(f'Unsupported step unit {unit!r}.')
                    period = (eccodes.codes_get(h, 'endStep') - eccodes.codes_get(h, 'startStep')) * STEP_SECONDS[unit]
                    if period <= 0:
                        raise ValueError(f'Message at {valid} is not an accumulation over a valid period. period = {period}')
                    data = data / period   # accumulation per period -> rate in <units_in>/s

                # If desired, negate
                if negate:
                    data = -data

                # Add to records
                records[valid] = data
            finally:
                eccodes.codes_release(h)
    if not records:
        raise ValueError(f'No GRIB messages found in {path}.')
    return lats, lons, sorted(records.items())