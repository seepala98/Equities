"""CSE listing data extractor.

This script uses undetected-chromedriver to access the CSE website and download
their XL        # Use environment variables for paths
        chrome_binary = os.getenv('CHROME_BIN', '/usr/bin/chromium')
        chromedriver_path = os.getenv('CHROMEDRIVER_PATH', '/usr/bin/chromedriver')
        
        options.binary_location = chrome_binary
        
        # Create Chrome driver with additional parameters
        driver = uc.Chrome(
            options=options,
            version_main=None,  # Let it auto-detect version
            driver_executable_path=chromedriver_path,
            browser_executable_path=chrome_binary,
            seleniumwire_options={'verify_ssl': False}  # Add this if needed for SSL issues
        )ompany listings.

Expected XLSX columns:
- Company: Company name
- Symbol: Trading symbol
- Industry: Industry classification
- Indices: Index membership
- Currency: Trading currency
- Trading: Trading status
- Tier: Listing tier
"""
import json
import time
import os
from datetime import datetime
from pathlib import Path
import undetected_chromedriver as uc
import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from xvfbwrapper import Xvfb
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from xvfbwrapper import Xvfb

def wait_and_find_element(driver, by, selector, timeout=10):
    """Wait for element to be present and clickable, then return it."""
    try:
        # First wait for presence
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
        # Then wait for it to be clickable
        return WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((by, selector))
        )
    except Exception as e:
        print(f'Error finding element {selector}: {e}')
        return None

def wait_for_download(directory, timeout=60):
    """Wait for an XLSX file to appear in the specified directory and be fully downloaded."""
    start_time = time.time()
    initial_files = set(Path(directory).glob('*.xlsx'))
    temp_pattern = '*.xlsx.crdownload'  # Chrome temporary download pattern
    
    while time.time() - start_time < timeout:
        # Check for both complete and in-progress downloads
        current_files = set(Path(directory).glob('*.xlsx'))
        temp_files = set(Path(directory).glob(temp_pattern))
        
        # First, wait for any temporary downloads to complete
        if temp_files:
            print("Download in progress...")
            time.sleep(2)
            continue
            
        # Then look for new completed files
        new_files = current_files - initial_files
        if new_files:
            downloaded_file = list(new_files)[0]
            # Wait a bit to ensure file is completely written
            time.sleep(2)
            return downloaded_file
            
        time.sleep(1)
        
    return None

def extract_cse_listings():
    """Download and process the CSE listings XLSX file.
    
    Returns a list of dicts with 'symbol' and 'name' keys.
    """
    
    # Create downloads directory in the airflow data directory
    download_dir = Path('/opt/airflow/data/cse/downloads')
    download_dir.mkdir(parents=True, exist_ok=True)
    
    options = uc.ChromeOptions()
    # Headless mode settings
    options.add_argument('--headless=new')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    
    # Disable automation detection
    options.add_argument('--disable-blink-features=AutomationControlled')
    
    # Additional required settings for Docker
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--disable-extensions')
    options.add_argument('--disable-web-security')
    
    # Allow downloads and popups
    options.add_argument('--disable-popup-blocking')
    prefs = {
        'download.default_directory': str(download_dir),
        'download.prompt_for_download': False,
        'download.directory_upgrade': True,
        'safebrowsing.enabled': False,
        'profile.default_content_settings.popups': 0,
        'profile.content_settings.exceptions.automatic_downloads.*.setting': 1,
        'safebrowsing.disable_download_protection': True,
        'plugins.always_open_pdf_externally': True,
    }
    options.add_experimental_option('prefs', prefs)
    
    # Additional ChromeDriver settings
    options.add_argument('--remote-debugging-port=9222')
    options.add_argument('--disable-setuid-sandbox')
    
    print('Starting browser...')
    try:
        # Use environment variables for paths
        chrome_binary = os.getenv('CHROME_BIN', '/usr/bin/chromium')
        chromedriver_path = os.getenv('CHROMEDRIVER_PATH', '/opt/chrome/driver/chromedriver')

        options.binary_location = chrome_binary

        # Create Chrome driver with additional parameters
        driver = uc.Chrome(
            options=options,
            version_main=None,  # Let it auto-detect version
            driver_executable_path=chromedriver_path,
            browser_executable_path=chrome_binary,
            seleniumwire_options={'verify_ssl': False}  # Add this if needed for SSL issues
        )
        driver.implicitly_wait(10)  # Set implicit wait
        print('Browser started successfully')
    except Exception as e:
        print(f'Error starting browser: {e}')
        raise
        
    listings = []
    
    try:
        print('Loading page...')
        time.sleep(5)  # Pre-navigation wait
        driver.get('https://thecse.com/listing/listed-companies/')
        
        print('Waiting for page load...')
        # Wait for body to be present to ensure basic page load
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        time.sleep(10)  # Additional wait for JavaScript initialization
        
        # Try to find and click the export button using the exact structure from the page
        export_button_selectors = [
            '//button[contains(@class, "inline-flex")][.//span[text()[contains(., "Export List")]] and .//span[contains(@class, "icon")]]',
            '//button[contains(@class, "text-blue-cse") and contains(., "Export List")]',
            '//button[contains(@id, "headlessui-menu-button")]',
            '//button[.//span[contains(text(), "Export")] and .//span[contains(@class, "icon")]]',
        ]
        
        export_btn = None
        for selector in export_button_selectors:
            try:
                print(f'Looking for export button with: {selector}')
                export_btn = wait_and_find_element(driver, By.XPATH, selector)
                if export_btn and export_btn.is_displayed() and export_btn.is_enabled():
                    print('Found export button!')
                    break
                else:
                    export_btn = None
            except Exception as e:
                print(f'Failed with selector {selector}: {e}')
                continue
        
        if export_btn:
            print('Clicking export button...')
            # Try a series of click methods with delays between attempts
            print('Attempting multi-step click...')
            
            # 1. Move to element first
            driver.execute_script("arguments[0].scrollIntoView(true);", export_btn)
            time.sleep(2)
            
            # 2. Try normal click first
            try:
                export_btn.click()
                print("Standard click successful")
            except Exception as e:
                print(f"Standard click failed: {e}")
                time.sleep(2)
                
                # 3. Try JavaScript click as fallback
                try:
                    driver.execute_script("arguments[0].click();", export_btn)
                    print("JavaScript click successful")
                except Exception as e:
                    print(f"JavaScript click failed: {e}")
                
                time.sleep(2)  # Wait for menu to appear
                
                # Look for XLSX download option in the dropdown
                xlsx_selectors = [
                    '//a[contains(@href, "export-listings/xlsx")]',
                    '//div[@role="menu"]//a[contains(text(), "XLSX")]',
                ]
                
                for selector in xlsx_selectors:
                    try:
                        xlsx_btn = wait_and_find_element(driver, By.XPATH, selector)
                        if xlsx_btn and xlsx_btn.is_displayed():
                            print('Found XLSX download link!')
                            try:
                                # Get the href attribute if it exists
                                href = xlsx_btn.get_attribute('href')
                                if href:
                                    print(f"Found direct download link: {href}")
                                    driver.get(href)  # Direct navigation to download URL
                                else:
                                    xlsx_btn.click()
                                print("XLSX download initiated")
                            except Exception as e:
                                print(f"Standard XLSX click failed: {e}")
                                try:
                                    driver.execute_script("arguments[0].click();", xlsx_btn)
                                    print("JavaScript XLSX click successful")
                                except Exception as e:
                                    print(f"JavaScript click failed: {e}")
                                    # Try one more time with direct navigation
                                    try:
                                        href = xlsx_btn.get_attribute('href')
                                        if href:
                                            driver.get(href)
                                            print("Direct navigation successful")
                                        else:
                                            continue
                                    except Exception as nav_e:
                                        print(f"Direct navigation failed: {nav_e}")
                                        continue
                            
                            print('Waiting for download...')
                            # Switch to the new tab if one was opened and handle download
                            original_window = driver.current_window_handle
                            
                            time.sleep(3)  # Wait for potential new tab
                            if len(driver.window_handles) > 1:
                                print("New tab detected, handling download...")
                                # Switch to new tab
                                for window_handle in driver.window_handles:
                                    if window_handle != original_window:
                                        driver.switch_to.window(window_handle)
                                        break
                                
                                time.sleep(5)  # Wait for new tab to fully load
                                
                                # Try to trigger download in new tab
                                try:
                                    download_links = driver.find_elements(By.XPATH, "//a[contains(@href, '.xlsx')]")
                                    if download_links:
                                        print("Found direct download link in new tab")
                                        download_links[0].click()
                                except Exception as e:
                                    print(f"Error in new tab: {e}")
                                
                                # Close new tab and switch back
                                driver.close()
                                driver.switch_to.window(original_window)
                            
                            time.sleep(10)  # Extended wait for download to start
                            xlsx_file = wait_for_download(str(download_dir))
                            
                            if xlsx_file:
                                print(f'Found downloaded file: {xlsx_file}')
                                
                                # Create new filename with date
                                date_str = time.strftime('%Y%m%d')
                                new_filename = download_dir / f'cse_listings_{date_str}.xlsx'
                                
                                # If file exists, add counter
                                counter = 1
                                while new_filename.exists():
                                    new_filename = download_dir / f'cse_listings_{date_str}_{counter}.xlsx'
                                    counter += 1
                                
                                # Move and rename the file
                                xlsx_file.rename(new_filename)
                                print(f'Renamed to: {new_filename}')
                                
                                # Read the XLSX file
                                df = pd.read_excel(new_filename)
                                
                                # Convert DataFrame rows to our listing format
                                for _, row in df.iterrows():
                                    # Map XLSX columns to database fields
                                    symbol = str(row.get('Symbol', '')).strip()
                                    name = str(row.get('Company', '')).strip()
                                    
                                    # Get trading status
                                    trading_status = str(row.get('Trading', '')).strip().lower()
                                    is_active = trading_status not in ['suspended', 'halted', 'delisted']
                                    
                                    if symbol and name and symbol.lower() != 'nan' and name.lower() != 'nan':
                                        listing = {
                                            'exchange': 'CSE',
                                            'symbol': symbol,
                                            'name': name,
                                            'listing_url': f'https://thecse.com/en/listings/{symbol}',
                                            'scraped_at': datetime.now().isoformat(),
                                            'status': trading_status if trading_status else 'listed',
                                            'active': is_active,
                                            'status_date': datetime.now().date().isoformat()
                                        }
                                        listings.append(listing)
                                
                                print(f'Successfully extracted {len(listings)} listings')
                                print(f'XLSX file saved as: {new_filename}')
                                break
                            else:
                                print('Download timed out')
                    except Exception as e:
                        print(f'Failed to handle XLSX download: {e}')
                        continue
                
            except Exception as e:
                print(f'Failed to handle export: {e}')
    
    except Exception as e:
        print(f'Error during extraction: {e}')
    
    finally:
        try:
            driver.quit()
        except:
            pass
    
    return listings

if __name__ == '__main__':
    print('Starting CSE listing extraction...')
    results = extract_cse_listings()
    print(f'\nFound {len(results)} listings')
    
    if results:
        # Print first few as sample
        print('\nFirst 10 listings:')
        for i, item in enumerate(results[:10], 1):
            print(f"{i}. {item['name']} - {item['symbol']}")
        
        # Save to JSON file
        out_file = Path(__file__).parent / 'data' / 'cse_listings.json'
        out_file.parent.mkdir(exist_ok=True)
        with open(out_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f'\nSaved {len(results)} listings to {out_file}')
