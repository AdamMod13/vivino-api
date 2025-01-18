import argparse
import json
import os
import utils.constants as c
from utils.requester import Requester

# Prices are in zł

# Wine_type_ids explain
# Red - 1
# White - 2
# Sparkling - 3
# Rose - 4
# Dessert - 7
# Fortified - 24

def get_arguments():
    """Gets arguments from the command line.

    Returns:
        A parser with the input arguments.
    """
    parser = argparse.ArgumentParser(usage='Scrape detailed wine data from Vivino.')

    parser.add_argument('output_file', help='Output .json file', type=str)
    parser.add_argument('-start_page', help='Starting page identifier', type=int, default=1)

    return parser.parse_args()

def load_existing_data(output_file):
    """Loads existing data from the output file if it exists."""
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r') as f:
                data = json.load(f)
                wines = data.get('wines', [])
                ids = {wine['id'] for wine in wines}  # Extract IDs for duplicate checking
                return wines, ids
        except json.JSONDecodeError:
            print("Existing file is corrupted or not a valid JSON. Starting fresh.")
            return [], set()
    return [], set()

def save_data_incrementally(output_file, new_wines, existing_ids):
    """Appends new wine data to the file and prints basic info."""
    if os.path.exists(output_file):
        existing_data, _ = load_existing_data(output_file)
    else:
        existing_data = []

    # Filter out duplicates
    filtered_wines = [wine for wine in new_wines if wine['id'] not in existing_ids]

    # Append the filtered new data to the existing data
    existing_data.extend(filtered_wines)

    # Write the combined data back to the file
    with open(output_file, 'w') as f:
        json.dump({'wines': existing_data}, f, indent=4)

    # Print information about each newly added wine
    for wine in filtered_wines:
        print(f"Saved wine: {wine['name']} ({wine.get('year', 'N/A')}) from {wine.get('region', 'N/A')} - Rating: {wine.get('rating', 'N/A')}/5")

    return {wine['id'] for wine in filtered_wines}  # Return IDs of saved wines


if __name__ == '__main__':
    # Gather the input arguments
    args = get_arguments()
    output_file = args.output_file
    start_page = args.start_page

    # Instantiate a wrapper over the `requests` package
    r = Requester(c.BASE_URL)

    # fr-france, it-italy, hr-croatia, gr-greece, de-germany, hu-hungary, ar-argentina, cl-chile, us-usa, pl-poland, pt-portugal, es-spain, at-austria, ch-switzerland

    # Define the payload with filters
    payload = {
        # "country_codes[]": "ch",
        # "food_ids[]": 20,
        # "grape_ids[]": 3,
        # "grape_filter": "varietal",
        "min_rating": 2.0,
        # "order_by": "ratings_average",
        # "order": "desc",
        # "price_range_min": 25,
        "price_range_max": 150,
        # "region_ids[]": 383,
    }

    # Load existing data and IDs
    existing_wines, existing_ids = load_existing_data(output_file)

    # Initial request to get the total number of matches
    res = r.get('explore/explore?', params=payload)
    n_matches = res.json().get('explore_vintage', {}).get('records_matched', 0)
    print(f'Number of matches: {n_matches}')

    # Iterate through the possible pages
    for i in range(start_page, max(1, int(n_matches / c.RECORDS_PER_PAGE)) + 1):
        payload['page'] = i
        print(f'Processing page: {payload["page"]}')

        # Fetch the wine matches for the current page
        res = r.get('explore/explore', params=payload)
        matches = res.json().get('explore_vintage', {}).get('matches', [])

        # Prepare a list to store the wines for this page
        new_wines = []

        # Iterate over every match (wine) on the current page
        for match in matches:
            print(match)
            # Extract detailed wine information
            wine = match['vintage']['wine']
            region_info = wine.get('region', None)
            country_info = region_info.get('country', {}) if region_info else {}
            region_info = match['vintage']['wine'].get('region', None)
            style_info = wine.get('style', None)

            if style_info and style_info.get('grapes'):
                grapes_names = style_info['grapes']
            else:
                grapes_names = []

            if region_info and region_info.get('country'):
                most_used_grapes = region_info['country'].get('most_used_grapes', [])
            else:
                most_used_grapes = []

            if grapes_names:
                most_used_grapes_name = grapes_names[0]['name']  # Use the first grape name from style
            elif most_used_grapes:
                most_used_grapes_name = most_used_grapes[0]['name']  # Fallback to the first most-used grape
            else:
                most_used_grapes_name = None

            wine_data = {
                'id': wine['id'],
                'name': wine['name'],
                'year': match['vintage'].get('year', None),
                'country': country_info.get('name', None) if country_info else None,
                'region': region_info.get('name', None) if region_info else None,
                'wine_type_id': wine['type_id'],
                'most_used_grapes': most_used_grapes_name,
                'winery': wine['winery']['name'] if wine.get('winery') else None,
                'rating': match['vintage']['statistics']['ratings_average'] if 'statistics' in match['vintage'] else None,
                'price': match['price']['amount'] if 'price' in match else None,
                'style': wine['style']['name'] if wine.get('style') else None,
            }

            # Add the wine data to the new_wines list
            new_wines.append(wine_data)

        # Save the data incrementally to the output file
        new_ids = save_data_incrementally(output_file, new_wines, existing_ids)
        existing_ids.update(new_ids)