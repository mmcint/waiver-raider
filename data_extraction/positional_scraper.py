import argparse
import requests
from bs4 import BeautifulSoup
import pandas as pd
import concurrent.futures
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def scrape_fantasypros(position, season):
    url = f"https://www.fantasypros.com/nfl/advanced-stats-{position}.php?year={season}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.find('table', {'id': 'data'})
        
        headers = [th.text for th in table.find_all('th')]
        rows = []
        for tr in table.find_all('tr')[1:]:
            rows.append([td.text for td in tr.find_all('td')])
        
        df = pd.DataFrame(rows, columns=headers)
        df['Season'] = season
        df['Position'] = position.upper()
        return df
    except requests.RequestException as e:
        logging.error(f"Error scraping {position.upper()} data for {season}: {str(e)}")
        return None
    except AttributeError as e:
        logging.error(f"Error parsing {position.upper()} data for {season}: {str(e)}")
        return None

def scrape_worker(args):
    position, season = args
    return scrape_fantasypros(position, season)

def save_to_excel(all_data, output_file):
    with pd.ExcelWriter(output_file, engine='xlsxwriter') as writer:
        positions = set()
        for df in all_data:
            if df is not None and 'Position' in df.columns:
                positions.update(df['Position'].unique())
        
        for position in positions:
            position_data = pd.concat([df for df in all_data if df is not None and 'Position' in df.columns and position in df['Position'].values], ignore_index=True)
            if not position_data.empty:
                position_data.to_excel(writer, sheet_name=position, index=False)
    logging.info(f"Data saved to {output_file} with separate tabs for each position")

def main():
    parser = argparse.ArgumentParser(description="Scrape FantasyPros advanced NFL stats")
    parser.add_argument("--positions", nargs="+", default=['qb', 'rb', 'wr', 'te'], help="Positions to scrape (default: qb rb wr te)")
    parser.add_argument("--start-year", type=int, default=2015, help="Start year for scraping (default: 2015)")
    parser.add_argument("--end-year", type=int, default=2024, help="End year for scraping (default: 2024)")
    parser.add_argument("--threads", type=int, default=4, help="Number of threads to use (default: 4)")
    parser.add_argument("--save-location", default=".", help="Directory to save the output file (default: current directory)")
    args = parser.parse_args()

    positions = args.positions
    seasons = range(args.start_year, args.end_year + 1)
    
    scrape_args = [(position, season) for position in positions for season in seasons]
    
    all_data = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.threads) as executor:
        future_to_args = {executor.submit(scrape_worker, arg): arg for arg in scrape_args}
        for future in concurrent.futures.as_completed(future_to_args):
            args = future_to_args[future]
            try:
                df = future.result()
                if df is not None:
                    all_data.append(df)
                    logging.info(f"Scraped {args[0].upper()} data for {args[1]}")
            except Exception as e:
                logging.error(f"Error processing {args[0].upper()} data for {args[1]}: {str(e)}")

    if all_data:
        output_filename = f"fantasypros_advanced_stats_{args.start_year}-{args.end_year}.xlsx"
        output_file = os.path.join(args.save_location, output_filename)
        os.makedirs(args.save_location, exist_ok=True)
        save_to_excel(all_data, output_file)
    else:
        logging.warning("No data was successfully scraped.")

if __name__ == "__main__":
    main()
