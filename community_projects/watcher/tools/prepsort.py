"""
PrepSort - A tool to sort AI training data prior to training.
This tool scans JSON files in date-organized directories, filters them based on criteria,
and copies matching MP4 files to an output directory.
"""

import argparse
import json
import os
import shutil
from datetime import datetime
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('prepsort')

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Sort AI training data based on JSON metadata.')
    parser.add_argument('--input', required=True, help='Root directory containing date-organized subdirectories with JSON and MP4 files')
    parser.add_argument('--output', required=True, help='Directory where matching MP4 files will be copied')
    parser.add_argument('--config', default='prepsort-config.json', help='Path to the filter criteria config file (default: prepsort-config.json)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    parser.add_argument('--clean', action='store_true', help='Clean output directory before copying files')
    return parser.parse_args()

def load_filter_criteria(config_path):
    """Load filter criteria from the config file."""
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Config file not found: {config_path}")
        exit(1)
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in config file: {config_path}")
        exit(1)

def matches_criteria(json_data, filter_criteria):
    """
    Check if the JSON data matches the filter criteria.
    
    Args:
        json_data (dict): The JSON data to check
        filter_criteria (dict): The filter criteria to match against
        
    Returns:
        bool: True if all criteria match, False otherwise
    """
    for key, value in filter_criteria.items():
        # Handle nested criteria with dot notation
        if '.' in key:
            parts = key.split('.')
            current = json_data
            for part in parts[:-1]:
                if part not in current:
                    return False
                current = current[part]
            if parts[-1] not in current or current[parts[-1]] != value:
                return False
        # Handle list values (any match)
        elif isinstance(value, list):
            if key not in json_data or json_data[key] not in value:
                return False
        # Handle simple key-value pairs
        elif key not in json_data or json_data[key] != value:
            return False
    return True

def clean_directory(directory_path):
    """
    Clean a directory by removing all files in it.
    
    Args:
        directory_path (str): Path to the directory to clean
    """
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)
        logger.info(f"Created output directory: {directory_path}")
        return
    
    # Count files to be removed
    files = [f for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f))]
    file_count = len(files)
    
    if file_count == 0:
        logger.info(f"Output directory {directory_path} is already empty")
        return
    
    # Remove all files
    for filename in files:
        file_path = os.path.join(directory_path, filename)
        try:
            os.remove(file_path)
        except Exception as e:
            logger.error(f"Error removing file {file_path}: {e}")
    
    logger.info(f"Cleaned output directory: {directory_path} ({file_count} files removed)")

def process_directory(root_dir, output_dir, filter_criteria, verbose=False):
    """
    Process all date-organized directories, find matching JSON files,
    and copy corresponding MP4 files to the output directory.
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Statistics counters
    total_json_files = 0
    matched_files = 0
    
    # Iterate through all date directories (YYYY-MM-DD format)
    for date_dir in sorted(os.listdir(root_dir)):
        date_path = os.path.join(root_dir, date_dir)
        
        # Skip if not a directory or not in date format
        if not os.path.isdir(date_path) or not is_date_format(date_dir):
            continue
            
        if verbose:
            logger.info(f"Processing directory: {date_dir}")
        
        # Process JSON files in the directory
        for filename in os.listdir(date_path):
            if filename.endswith('.json'):
                total_json_files += 1
                json_path = os.path.join(date_path, filename)
                
                # Parse the JSON file
                try:
                    with open(json_path, 'r') as f:
                        json_data = json.load(f)
                except Exception as e:
                    logger.warning(f"Error parsing {json_path}: {e}")
                    continue
                
                # Check if it matches the filter criteria
                if json_data and matches_criteria(json_data, filter_criteria):
                    # Find the corresponding MP4 file
                    base_name = os.path.splitext(filename)[0]
                    mp4_filename = f"{base_name}.mp4"
                    mp4_path = os.path.join(date_path, mp4_filename)
                    
                    if os.path.exists(mp4_path):
                        # Copy the MP4 file to the output directory
                        try:
                            shutil.copy2(mp4_path, output_dir)
                            matched_files += 1
                            if verbose:
                                logger.info(f"Matched and copied: {mp4_filename}")
                        except Exception as e:
                            logger.error(f"Error copying {mp4_path}: {e}")
                    else:
                        logger.warning(f"No matching MP4 file found for {json_path}")
    
    # Print summary
    logger.info(f"Processed {total_json_files} JSON files")
    logger.info(f"Found {matched_files} matching files and copied them to {output_dir}")
    
    return matched_files

def is_date_format(dirname):
    """Check if directory name follows YYYYMMDD format."""
    try:
        datetime.strptime(dirname, '%Y%m%d')
        return True
    except ValueError:
        return False

def main():
    """Main function for the prepsort tool."""
    args = parse_args()
    
    # Set log level
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Validate input directory
    if not os.path.isdir(args.input):
        logger.error(f"Input directory does not exist: {args.input}")
        exit(1)
    
    # Clean output directory if requested
    if args.clean:
        clean_directory(args.output)
    
    # Load filter criteria
    filter_criteria = load_filter_criteria(args.config)
    logger.info(f"Loaded filter criteria from {args.config}")
    
    # Process all directories
    matched_count = process_directory(args.input, args.output, filter_criteria, args.verbose)
    
    if matched_count > 0:
        logger.info("Sort completed successfully!")
        return 0
    else:
        logger.warning("No matching files found.")
        return 1

if __name__ == "__main__":
    exit(main())

