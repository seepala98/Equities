"""Handler for CSE listings in the airflow DAG."""
import json
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_batch

def process_cse_listings(**context):
    """Process CSE listings using the external extractor."""
    try:
        # Import the extractor from the scripts directory
        import sys
        from pathlib import Path
        
        # Add scripts directory to Python path
        scripts_dir = Path(__file__).resolve().parent.parent / 'scripts'
        if str(scripts_dir) not in sys.path:
            sys.path.append(str(scripts_dir))
        
        from cse_extractor import extract_cse_listings
        
        # Get listings from CSE
        listings = extract_cse_listings()
        
        if not listings:
            raise ValueError("No listings were extracted")
            
        # Connect to PostgreSQL
        conn = psycopg2.connect(
            host="db",  # Docker service name
            database="postgres",
            user="postgres",
            password="postgres"
        )
        
        try:
            with conn.cursor() as cur:
                # First, mark all existing CSE listings as inactive
                cur.execute("""
                    UPDATE stocks_listing 
                    SET active = false 
                    WHERE exchange = 'CSE'
                """)
                
                # Prepare data for insert/update
                insert_query = """
                    INSERT INTO stocks_listing 
                        (exchange, symbol, name, listing_url, scraped_at, status, active, status_date)
                    VALUES 
                        (%(exchange)s, %(symbol)s, %(name)s, %(listing_url)s, %(scraped_at)s, 
                         %(status)s, %(active)s, %(status_date)s)
                    ON CONFLICT (exchange, symbol) DO UPDATE SET
                        name = EXCLUDED.name,
                        listing_url = EXCLUDED.listing_url,
                        scraped_at = EXCLUDED.scraped_at,
                        status = EXCLUDED.status,
                        active = EXCLUDED.active,
                        status_date = EXCLUDED.status_date
                """
                
                # Execute batch insert/update
                execute_batch(cur, insert_query, listings)
                
                # Commit the transaction
                conn.commit()
                
        finally:
            conn.close()
            
        # Create result string for XCom
        result = f"Found and processed {len(listings)} CSE entries"
        
        # Save to a dated JSON file for backup
        date_str = datetime.now().strftime('%Y%m%d')
        output_dir = Path(__file__).parent.parent / 'data' / 'cse'
        output_dir.mkdir(parents=True, exist_ok=True)
        
        output_file = output_dir / f'cse_listings_{date_str}.json'
        with open(output_file, 'w') as f:
            json.dump(listings, f, indent=2)
            
        return result
        
    except Exception as e:
        print(f"Error processing CSE listings: {e}")
        raise
