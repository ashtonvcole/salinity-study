import argparse
import cdsapi
from dotenv import load_dotenv
import json
import os

def main():
    parser = argparse.ArgumentParser(description='A script to retrieve ERA5 data through their API.')
    parser.add_argument('input', help='Input request JSON')
    parser.add_argument('-o', '--output', default=None,
                        help='Output file name (default: name chosen by the CDS server)')
    parser.add_argument('--url', default=None,
                        help='CDS API URL (overrides CDSAPI_URL from environment/.env)')
    parser.add_argument('--key', default=None,
                        help='CDS API key (overrides CDSAPI_KEY from environment/.env)')
    args = parser.parse_args()
    with open(args.input) as f:
        data_request = json.load(f)
    # Precedence: command-line option > environment/.env > ~/.cdsapirc (cdsapi fallback)
    load_dotenv()
    url = args.url or os.getenv('CDSAPI_URL')
    key = args.key or os.getenv('CDSAPI_KEY')
    client = cdsapi.Client(url=url, key=key)
    client.retrieve(data_request['dataset'], data_request['request']).download(args.output)

if __name__ == '__main__':
    main()
