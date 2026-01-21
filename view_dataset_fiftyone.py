#!/usr/bin/env python3
"""
View the garage door classification dataset using FiftyOne.

This script loads all images from the dataset directory (organized by class)
and opens them in the FiftyOne interactive viewer.
"""

import fiftyone as fo
from pathlib import Path

# Setup dataset directory
SCRIPT_DIR = Path(__file__).parent
DATASET_DIR = SCRIPT_DIR / "dataset"

def main():
    if not DATASET_DIR.exists():
        print(f"Dataset directory not found at {DATASET_DIR}")
        print("No images have been collected yet.")
        return
    
    # Check if there are any images
    image_count = len(list(DATASET_DIR.glob("*/*.jpg")))
    if image_count == 0:
        print(f"No images found in {DATASET_DIR}")
        return
    
    print(f"Found {image_count} images in dataset")
    print(f"Loading dataset from {DATASET_DIR}...")
    
    # Create dataset from directory structure
    # FiftyOne automatically detects labels from subdirectory names
    dataset = fo.Dataset.from_dir(
        dataset_dir=str(DATASET_DIR),
        dataset_type=fo.types.ImageClassificationDirectoryTree,
        name="garage_door_classification"
    )
    
    print(f"Dataset loaded with {len(dataset)} samples")
    print("\nOpening FiftyOne App...")
    
    # Launch the interactive viewer
    session = fo.launch_app(dataset)
    session.wait()

if __name__ == "__main__":
    main()
