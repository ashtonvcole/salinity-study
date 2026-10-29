import datetime as dt
import re
import numpy as np

# A record header, e.g.
# iLat=  70iLong=  40DX= 1.000DY= 1.000SWLat=   0.375SWLon= -99.625DT=202108010000
# Fields are matched by label instead of by column, so differing widths and
# precisions between OWI writers are tolerated.
RECORD_HEADER = re.compile(
    r'iLat=\s*(\d+)\s*iLong=\s*(\d+)\s*'
    r'DX=\s*([-+.\d]+)\s*DY=\s*([-+.\d]+)\s*'
    r'SWLat=\s*([-+.\d]+)\s*SWLon=\s*([-+.\d]+)\s*'
    r'DT=\s*(\d+)'
)

def parse_owi_date(text: str) -> dt.datetime:
    """Convert an OWI date string to a datetime.

    Arguments:
        text (str): A date as YYYYMMDDHH or YYYYMMDDHHMM.

    Returns:
        datetime.datetime: The date, with minutes taken as zero if omitted.
    """
    text = text.strip()
    if len(text) == 10:
        text += '00'
    return dt.datetime.strptime(text, '%Y%m%d%H%M')

def write_owi_header(f, title: str, start_date: dt.datetime, end_date: dt.datetime):
    """Write standard header for an OWI formatted file.

    Arguments:
        f: A file object.
        title (str): A descriptive title.
        start_date (datetime.datetime): The starting date of the time series.
        end_date (datetime.datetime): The ending date of the time series.
    """
    f.write(
        f'{title:<55}' +
        f'{start_date.strftime('%Y%m%d%H'):<10}' +
        ' ' * 5 +
        f'{end_date.strftime('%Y%m%d%H'):<10}\n'
    )

def write_owi_data(f, ilat: int, ilon: int, dx: float, dy: float, swlat: float,
    swlon: float, date: dt.datetime, data: np.ndarray):
    """Write a single time series record to file.

    A record consists of a grid definition and a sequence of values for each
    grid point. Note that this means each record may be defined on a new grid,
    although this is inefficient for ADCIRC or DGSWEM to re-compute.

    Arguments:
        ilat (int): The number of horizontal parallels.
        ilon (int): The number of vertical meridians.
        dx (float): The horizontal/longitudnal spacing of the data grid.
        dy (float): The vertical/latitudnal spacing of the data grid.
        swlat (float): The latitude of the southwest corner of the data grid.
        swlon (float): The longitude of the southwest corner of the data grid.
        date (datetime.datetime): The time of the record.
        data (np.ndarray): Flattened values, longitude varying fastest and
            latitude increasing from south to north.
    """
    # Write record header
    f.write(f'iLat={ilat:4d}iLong={ilon:4d}DX={dx:6.3f}DY={dy:6.3f}SWLat={swlat:8.3f}SWLon={swlon:8.3f}DT={date.strftime('%Y%m%d%H%M'):<12}\n')
    # Write data
    # Format is 8 entries per row, each 10 charaters long, 10.3g
    # This requires splitting into full and
    num_filled_entries = (data.size // 8) * 8
    num_tail_entries = data.size % 8
    data_filled = data[:num_filled_entries].reshape(-1, 8)
    data_tail = data[num_filled_entries:]
    if num_filled_entries > 0:
        np.savetxt(f, data_filled, fmt='%10.3g', delimiter='')
    if num_tail_entries > 0:
        f.write(('%10.3g' * num_tail_entries) % tuple(data_tail) + '\n')

def read_owi_header(f) -> tuple[str, dt.datetime, dt.datetime]:
    """Read standard header from an OWI formatted file.

    This is the complement of write_owi_header. It reads the first line, so the
    file object should be positioned at the start of the file.

    Arguments:
        f: A file object.

    Returns:
        tuple[str, datetime.datetime, datetime.datetime]:
            - title (str): The descriptive title.
            - start_date (datetime.datetime): The starting date of the time series.
            - end_date (datetime.datetime): The ending date of the time series.
    """
    line = f.readline()
    if not line:
        raise ValueError('File is empty.')
    # Title in columns 1-55, start date in 56-65, end date in 71-80
    return (
        line[:55].strip(),
        parse_owi_date(line[55:65]),
        parse_owi_date(line[70:80])
    )

def read_owi_data(f) -> tuple[int, int, float, float, float, float,
    dt.datetime, np.ndarray] | None:
    """Read a single time series record from file.

    This is the complement of write_owi_data. It reads from the file object's
    current position, which should be at a record header, and leaves it at the
    next record header. Calling it repeatedly after read_owi_header reads
    successive records.

    A record may hold more than one field, e.g. wind u and v. The number of
    fields is not stored, so the values of all fields are returned together.

    Arguments:
        f: A file object.

    Returns:
        tuple[int, int, float, float, float, float, datetime.datetime, np.ndarray] | None:
            None if there are no more records. Otherwise:
            - ilat (int): The number of horizontal parallels.
            - ilon (int): The number of vertical meridians.
            - dx (float): The horizontal/longitudnal spacing of the data grid.
            - dy (float): The vertical/latitudnal spacing of the data grid.
            - swlat (float): The latitude of the southwest corner of the data grid.
            - swlon (float): The longitude of the southwest corner of the data grid.
            - date (datetime.datetime): The time of the record.
            - data (np.ndarray): Flattened values, longitude varying fastest and
              latitude increasing from south to north. Fields are concatenated,
              so the length is a multiple of ilat * ilon.
    """
    # Read record header, skipping blank lines
    line = f.readline()
    while line and not line.strip():
        line = f.readline()
    if not line:
        return None
    match = RECORD_HEADER.match(line)
    if match is None:
        raise ValueError(f'Expected an OWI record header, got: {line.strip()!r}')
    ilat, ilon = int(match.group(1)), int(match.group(2))
    dx, dy, swlat, swlon = (float(match.group(i)) for i in range(3, 7))
    date = parse_owi_date(match.group(7))

    # Read data
    # Rows of 10 character values, up to the next record header or the end of the file
    values = []
    while True:
        position = f.tell()
        line = f.readline()
        if not line:
            break
        if line.startswith('iLat'):
            f.seek(position)
            break
        row = line.rstrip('\r\n')
        values += [float(row[i:i + 10]) for i in range(0, len(row), 10) if row[i:i + 10].strip()]
    if len(values) == 0 or len(values) % (ilat * ilon) != 0:
        raise ValueError(
            f'Record {date} has {len(values)} values, '
            f'which is not a multiple of {ilat} x {ilon} = {ilat * ilon}.'
        )
    return ilat, ilon, dx, dy, swlat, swlon, date, np.array(values)