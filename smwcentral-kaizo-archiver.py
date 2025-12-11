#!/usr/bin/env python3
# kaizo_archiver.py
#
# Description:
#   Archives Kaizo hacks of specified difficulty levels from SMWCentral via its public API.
#   Downloads .zip files, extracts only .bps files, and patches them using FLIPS.
#   Uses new API endpoints and file naming schema.
#
# Usage Examples:
#   1) Fetch only Newcomer Kaizo hacks:
#        ./kaizo_archiver.py --newcomer
#   2) Fetch multiple difficulties:
#        ./kaizo_archiver.py --newcomer --casual --expert
#   3) Fetch all Kaizo difficulties plus awaiting moderation:
#        ./kaizo_archiver.py --all --awaiting
#
# Options:
#   -h, --help            Show this help message and exit
#   --newcomer            Fetch Newcomer (diff_1) Kaizo hacks
#   --casual              Fetch Casual (diff_2) Kaizo hacks
#   --intermediate        Fetch Intermediate (diff_3) Kaizo hacks
#   --advanced            Fetch Advanced (diff_4) Kaizo hacks
#   --expert              Fetch Expert (diff_5) Kaizo hacks
#   --master              Fetch Master (diff_6) Kaizo hacks
#   --grandmaster         Fetch Grandmaster (diff_7) Kaizo hacks
#   --awaiting            Fetch hacks that are awaiting moderation
#   --all                 Fetch all Kaizo difficulty levels
#   --base-dir BASE_DIR   Where to store downloaded hacks (default: current dir)
#   --clean-rom PATH      Path to a clean SMC ROM for patching (default: clean.smc)
#   --flips PATH          Path to your FLIPS executable (default: ./flips)
#

import argparse
import hashlib
import json
import logging
import os
import re
import requests
import shutil
import subprocess
import sys
import time
import urllib.parse
import zipfile
from datetime import datetime
from pathlib import Path

# ----------------------------------------------
# Constants for SMWCentral Kaizo endpoints
# ----------------------------------------------
BASE_URL = "https://www.smwcentral.net/ajax.php?a=getsectionlist&s=smwhacks"

DIFFICULTY_MAP = {
    "newcomer": ("diff_1", "Newcomer"),
    "casual": ("diff_2", "Casual"),
    "intermediate": ("diff_3", "Intermediate"),
    "advanced": ("diff_4", "Advanced"),
    "expert": ("diff_5", "Expert"),
    "master": ("diff_6", "Master"),
    "grandmaster": ("diff_7", "Grandmaster")
}

# ----------------------------------------------
# Logging Setup
# ----------------------------------------------
def setup_logging(log_dir):
    """Setup logging configuration."""
    log_file = os.path.join(log_dir, f"kaizo_archiver_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    
    # Create formatters
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_formatter = logging.Formatter('%(message)s')
    
    # Setup file handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(file_formatter)
    
    # Setup console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)
    
    # Setup logger
    logger = logging.getLogger('kaizo_archiver')
    logger.setLevel(logging.DEBUG)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger, log_file

# ----------------------------------------------
# Argument Parsing
# ----------------------------------------------
def parse_args():
    parser = argparse.ArgumentParser(
        description="Archive Kaizo hacks from SMWCentral. Downloads, extracts .bps files, and patches them."
    )

    parser.add_argument("--all", action="store_true",
                       help="Fetch all Kaizo difficulty levels.")
    parser.add_argument("--newcomer", action="store_true",
                        help="Fetch Newcomer (diff_1) Kaizo hacks.")
    parser.add_argument("--casual", action="store_true",
                        help="Fetch Casual (diff_2) Kaizo hacks.")
    parser.add_argument("--intermediate", action="store_true",
                        help="Fetch Intermediate (diff_3) Kaizo hacks.")
    parser.add_argument("--advanced", action="store_true",
                        help="Fetch Advanced (diff_4) Kaizo hacks.")
    parser.add_argument("--expert", action="store_true",
                        help="Fetch Expert (diff_5) Kaizo hacks.")
    parser.add_argument("--master", action="store_true",
                        help="Fetch Master (diff_6) Kaizo hacks.")
    parser.add_argument("--grandmaster", action="store_true",
                        help="Fetch Grandmaster (diff_7) Kaizo hacks.")
    parser.add_argument("--awaiting", action="store_true",
                        help="Fetch hacks that are awaiting moderation.")
    parser.add_argument("--base-dir", default=".",
                        help="Base directory where hacks will be saved (default: current directory).")
    parser.add_argument("--clean-rom", default="clean.smc",
                        help="Path to a clean .smc file for patching (default: clean.smc).")
    parser.add_argument("--flips", default="./flips",
                        help="Path to the flips executable (default: ./flips).")

    return parser.parse_args()

# ----------------------------------------------
# Helper Functions
# ----------------------------------------------
def ensure_dir_exists(path):
    """Create directory if it does not exist."""
    Path(path).mkdir(parents=True, exist_ok=True)

def sanitize_filename(filename):
    """Removes or replaces invalid filename characters."""
    # Replace problematic characters
    filename = re.sub(r'[<>:"/\\|?*]', "_", filename)
    # Remove or replace other potentially problematic characters
    filename = filename.replace('\n', ' ').replace('\r', ' ')
    # Collapse multiple spaces/underscores
    filename = re.sub(r'[_\s]+', ' ', filename).strip()
    return filename

def get_short_hash(data, length=6):
    """Generate a short hash from data."""
    return hashlib.md5(data).hexdigest()[:length]

def build_endpoint_url(difficulty_code=None, is_awaiting=False):
    """Build the API endpoint URL based on parameters."""
    if is_awaiting:
        return f"{BASE_URL}&u=1&f[type][]=kaizo"
    else:
        return f"{BASE_URL}&f[difficulty][]={difficulty_code}&f[type][]=kaizo"

# ----------------------------------------------
# Fetch Page URLs
# ----------------------------------------------
def fetch_all_data(initial_url, logger):
    """
    Fetch all data from paginated API endpoint.
    Returns a list of all items from all pages.
    """
    all_items = []
    next_url = initial_url
    page_num = 1

    while next_url:
        logger.info(f"Fetching page {page_num}: {next_url}")
        try:
            response = requests.get(next_url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                items = data.get("data", [])
                all_items.extend(items)
                logger.debug(f"Page {page_num}: Found {len(items)} items")
                
                next_url = data.get("next_page_url")
                page_num += 1
                time.sleep(1)  # Be nice to the server
            else:
                logger.error(f"Failed to retrieve data: HTTP {response.status_code}")
                break
        except Exception as e:
            logger.error(f"Error fetching page {page_num}: {e}")
            break

    logger.info(f"Total items fetched: {len(all_items)}")
    return all_items

# ----------------------------------------------
# Format filename based on hack metadata
# ----------------------------------------------
def format_filename(item_data, original_filename):
    """
    Format: "name - authors - type - difficulty - length - original decoded filename"
    """
    try:
        name = sanitize_filename(item_data.get("name", "Unknown"))
        
        # Handle multiple authors
        authors = item_data.get("authors", [])
        if authors:
            author_names = [sanitize_filename(author.get("name", "Unknown")) for author in authors]
            authors_str = " & ".join(author_names)
        else:
            authors_str = "Unknown"
        
        # Get fields
        fields = item_data.get("fields", {})
        hack_type = sanitize_filename(fields.get("type", "Unknown"))
        difficulty = sanitize_filename(fields.get("difficulty", "Unknown"))
        length = sanitize_filename(fields.get("length", "Unknown"))
        
        # Decode original filename
        decoded_original = urllib.parse.unquote(original_filename)
        
        # Build the new filename
        parts = [name, authors_str, hack_type, difficulty, length, decoded_original]
        return " - ".join(parts)
    except Exception as e:
        return sanitize_filename(urllib.parse.unquote(original_filename))

# ----------------------------------------------
# Download & Extract Logic
# ----------------------------------------------
def download_and_extract_bps(item_data, download_url, zip_dir, bps_dir, logger):
    """
    Download a ZIP file and extract only .bps files with new naming schema.
    Returns a dict with status information.
    """
    result = {
        'success': False,
        'download_success': False,
        'bps_count': 0,
        'bps_files': [],
        'error': None,
        'requires_login': False
    }
    
    try:
        # Get original filename from URL
        original_filename = download_url.split('/')[-1]
        decoded_filename = urllib.parse.unquote(original_filename)
        
        # Format the new base filename
        base_name = format_filename(item_data, original_filename)
        
        # Download the ZIP file
        zip_path = os.path.join(zip_dir, decoded_filename)
        
        logger.info(f"Downloading: {decoded_filename}")
        resp = requests.get(download_url, stream=True, timeout=60)
        
        if resp.status_code == 403:
            logger.warning(f"Access denied (403) - likely requires login: {decoded_filename}")
            result['requires_login'] = True
            result['error'] = "Requires login (age verification)"
            return result
        elif resp.status_code != 200:
            logger.error(f"Failed to download: {download_url} (HTTP {resp.status_code})")
            result['error'] = f"HTTP {resp.status_code}"
            return result
        
        # Save the file
        with open(zip_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        logger.info(f"Downloaded successfully: {decoded_filename}")
        result['download_success'] = True
        
        # Extract only .bps files
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                bps_members = [m for m in zip_ref.namelist() if m.lower().endswith('.bps')]
                
                if not bps_members:
                    logger.warning(f"No .bps files found in {decoded_filename}")
                    result['success'] = True  # Download was successful, just no BPS files
                    return result
                
                logger.debug(f"Found {len(bps_members)} .bps files in {decoded_filename}")
                
                for idx, member in enumerate(bps_members):
                    # Read the BPS file content
                    bps_content = zip_ref.read(member)
                    
                    # Generate filename
                    if len(bps_members) == 1:
                        # Single BPS file - no hash needed
                        new_bps_name = base_name.replace(decoded_filename, 
                                                        decoded_filename.replace('.zip', '.bps'))
                    else:
                        # Multiple BPS files - add hash
                        hash_suffix = get_short_hash(bps_content)
                        new_bps_name = base_name.replace(decoded_filename, 
                                                        decoded_filename.replace('.zip', f'_{hash_suffix}.bps'))
                    
                    # Write the BPS file
                    bps_path = os.path.join(bps_dir, new_bps_name)
                    with open(bps_path, 'wb') as f:
                        f.write(bps_content)
                    
                    logger.debug(f"Extracted: {os.path.basename(member)} -> {os.path.basename(new_bps_name)}")
                    result['bps_files'].append(bps_path)
                
                result['bps_count'] = len(result['bps_files'])
                result['success'] = True
                    
        except zipfile.BadZipFile:
            logger.error(f"{zip_path} is not a valid zip file.")
            result['error'] = "Invalid ZIP file"
        except Exception as e:
            logger.error(f"Error extracting {decoded_filename}: {e}")
            result['error'] = f"Extraction error: {str(e)}"
            
        return result
        
    except Exception as e:
        logger.error(f"Error processing {download_url}: {e}")
        result['error'] = f"Processing error: {str(e)}"
        return result

# ----------------------------------------------
# Patch .bps files
# ----------------------------------------------
def patch_bps_file(bps_path, patched_dir, flips_path, clean_rom, logger):
    """
    Patch a single .bps file using FLIPS.
    """
    try:
        bps_filename = os.path.basename(bps_path)
        output_filename = bps_filename.replace('.bps', '.smc')
        output_path = os.path.join(patched_dir, output_filename)
        
        cmd = [flips_path, "-a", bps_path, clean_rom, output_path]
        
        logger.debug(f"Patching: {bps_filename}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.debug(f"Successfully patched: {bps_filename}")
            return True
        else:
            logger.error(f"Failed to patch {bps_filename}: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Error patching {bps_path}: {e}")
        return False

# ----------------------------------------------
# Save JSON data
# ----------------------------------------------
def save_json_data(data, filepath, logger):
    """Save data as JSON file."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved JSON data to {filepath}")
    except Exception as e:
        logger.error(f"Failed to save JSON data: {e}")

# ----------------------------------------------
# Generate summary report
# ----------------------------------------------
def generate_summary_report(stats, report_path, logger):
    """Generate a summary report of the archiving process."""
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("SMWCentral Kaizo Archive Summary Report\n")
            f.write("=" * 50 + "\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for difficulty, data in stats.items():
                f.write(f"\n{difficulty.upper()}\n")
                f.write("-" * 30 + "\n")
                f.write(f"Total hacks: {data['total_hacks']}\n")
                f.write(f"Successfully downloaded: {data['downloaded']}\n")
                f.write(f"Failed downloads: {data['failed_downloads']}\n")
                f.write(f"Requires login: {data['requires_login']}\n")
                f.write(f"Total BPS files extracted: {data['total_bps']}\n")
                f.write(f"Successfully patched: {data['patched']}\n")
                f.write(f"Failed patches: {data['failed_patches']}\n")
                
                if data['login_required_hacks']:
                    f.write("\nHacks requiring manual download (login required):\n")
                    for hack in data['login_required_hacks']:
                        f.write(f"  - {hack['name']} by {hack['authors']}\n")
                        f.write(f"    URL: {hack['url']}\n")
                
                if data['failed_hacks']:
                    f.write("\nFailed downloads:\n")
                    for hack in data['failed_hacks']:
                        f.write(f"  - {hack['name']}: {hack['error']}\n")
                
                f.write("\n")
        
        logger.info(f"Summary report saved to {report_path}")
    except Exception as e:
        logger.error(f"Failed to generate summary report: {e}")

# ----------------------------------------------
# Main Logic
# ----------------------------------------------
def main():
    args = parse_args()
    
    # Get current date for folder naming
    date_str = datetime.now().strftime("%Y%m%d")
    
    # Setup base logging directory
    base_dir = os.path.abspath(args.base_dir)
    log_dir = os.path.join(base_dir, "logs")
    ensure_dir_exists(log_dir)
    
    # Setup logging
    logger, log_file = setup_logging(log_dir)
    logger.info("Starting SMWCentral Kaizo Archiver")
    logger.info(f"Log file: {log_file}")
    
    # Determine which endpoints to fetch
    endpoints = []
    
    if args.all:
        for key, (diff_code, label) in DIFFICULTY_MAP.items():
            endpoints.append((build_endpoint_url(diff_code), label.lower()))
    else:
        for key, (diff_code, label) in DIFFICULTY_MAP.items():
            if getattr(args, key):
                endpoints.append((build_endpoint_url(diff_code), label.lower()))
    
    if args.awaiting:
        endpoints.append((build_endpoint_url(is_awaiting=True), "awaiting"))
    
    if not endpoints:
        logger.error("No difficulties selected. Use --newcomer, --casual, etc., --all, or --awaiting.")
        sys.exit(0)
    
    # Check if clean ROM exists
    if not os.path.exists(args.clean_rom):
        logger.error(f"Clean ROM not found at {args.clean_rom}")
        sys.exit(1)
    
    # Check if FLIPS exists
    if not os.path.exists(args.flips):
        logger.error(f"FLIPS not found at {args.flips}")
        sys.exit(1)
    
    # Global statistics
    global_stats = {}
    
    # Process each endpoint
    for endpoint_url, difficulty_label in endpoints:
        logger.info(f"\n{'='*50}")
        logger.info(f"Processing {difficulty_label.title()} Kaizo Hacks")
        logger.info(f"{'='*50}")
        
        # Initialize statistics for this difficulty
        stats = {
            'total_hacks': 0,
            'downloaded': 0,
            'failed_downloads': 0,
            'requires_login': 0,
            'total_bps': 0,
            'patched': 0,
            'failed_patches': 0,
            'login_required_hacks': [],
            'failed_hacks': []
        }
        
        # Create folder structure
        main_folder = f"smwcentral-kaizo-archive-{difficulty_label}-{date_str}"
        main_path = os.path.join(base_dir, main_folder)
        zip_dir = os.path.join(main_path, f"{main_folder}-zips")
        bps_dir = os.path.join(main_path, f"{main_folder}-bps")
        patched_dir = os.path.join(main_path, f"{main_folder}-patched")
        
        ensure_dir_exists(zip_dir)
        ensure_dir_exists(bps_dir)
        ensure_dir_exists(patched_dir)
        
        # Fetch all data
        all_items = fetch_all_data(endpoint_url, logger)
        
        # Save JSON data for later analysis
        json_path = os.path.join(main_path, f"{main_folder}-data.json")
        save_json_data(all_items, json_path, logger)
        
        # Process each hack
        for idx, item in enumerate(all_items, 1):
            hack_name = item.get("name", "Unknown")
            download_url = item.get("download_url")
            
            if not download_url:
                logger.warning(f"No download URL for hack: {hack_name}")
                continue
            
            stats['total_hacks'] += 1
            logger.info(f"\n[{idx}/{len(all_items)}] Processing: {hack_name}")
            
            # Get author info for logging
            authors = item.get("authors", [])
            author_names = " & ".join([author.get("name", "Unknown") for author in authors])
            
            # Download and extract BPS files
            result = download_and_extract_bps(item, download_url, zip_dir, bps_dir, logger)
            
            if result['requires_login']:
                stats['requires_login'] += 1
                stats['login_required_hacks'].append({
                    'name': hack_name,
                    'authors': author_names,
                    'url': download_url
                })
                logger.warning(f"Manual download required for: {hack_name}")
            elif not result['download_success']:
                stats['failed_downloads'] += 1
                stats['failed_hacks'].append({
                    'name': hack_name,
                    'error': result['error']
                })
            else:
                stats['downloaded'] += 1
                stats['total_bps'] += result['bps_count']
                
                # Log extraction results
                if result['bps_count'] > 0:
                    logger.info(f"Extracted {result['bps_count']} BPS file(s) from {hack_name}")
                else:
                    logger.warning(f"No BPS files found in {hack_name}")
                
                # Patch each BPS file
                patches_success = 0
                patches_failed = 0
                
                for bps_file in result['bps_files']:
                    if patch_bps_file(bps_file, patched_dir, args.flips, args.clean_rom, logger):
                        patches_success += 1
                    else:
                        patches_failed += 1
                
                stats['patched'] += patches_success
                stats['failed_patches'] += patches_failed
                
                if patches_success > 0:
                    logger.info(f"Successfully patched {patches_success}/{result['bps_count']} file(s) for {hack_name}")
            
            # Small delay between downloads
            time.sleep(0.5)
        
        # Log summary for this difficulty
        logger.info(f"\n{difficulty_label.title()} Summary:")
        logger.info(f"  Total hacks: {stats['total_hacks']}")
        logger.info(f"  Downloaded: {stats['downloaded']}")
        logger.info(f"  Failed: {stats['failed_downloads']}")
        logger.info(f"  Requires login: {stats['requires_login']}")
        logger.info(f"  Total BPS files: {stats['total_bps']}")
        logger.info(f"  Patched: {stats['patched']}")
        logger.info(f"  Failed patches: {stats['failed_patches']}")
        
        # Store stats for global report
        global_stats[difficulty_label] = stats
    
    # Generate final summary report
    summary_path = os.path.join(base_dir, f"kaizo_archive_summary_{date_str}.txt")
    generate_summary_report(global_stats, summary_path, logger)
    
    # Log final summary
    logger.info("\n" + "="*50)
    logger.info("ARCHIVING COMPLETE")
    logger.info("="*50)
    
    total_hacks = sum(s['total_hacks'] for s in global_stats.values())
    total_downloaded = sum(s['downloaded'] for s in global_stats.values())
    total_login_required = sum(s['requires_login'] for s in global_stats.values())
    total_bps = sum(s['total_bps'] for s in global_stats.values())
    total_patched = sum(s['patched'] for s in global_stats.values())
    
    logger.info(f"Total hacks processed: {total_hacks}")
    logger.info(f"Successfully downloaded: {total_downloaded}")
    logger.info(f"Requires manual download: {total_login_required}")
    logger.info(f"Total BPS files extracted: {total_bps}")
    logger.info(f"Total patches created: {total_patched}")
    logger.info(f"\nSummary report: {summary_path}")
    logger.info(f"Log file: {log_file}")

if __name__ == "__main__":
    main()