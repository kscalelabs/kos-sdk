import os
import argparse

# Mapping of old joint names to new joint names
REPLACE_MAP = {
    "left_knee_pitch": "left_knee",
    "left_ankle_pitch": "left_ankle",
    "right_knee_pitch": "right_knee",
    "right_ankle_pitch": "right_ankle",
}

# Only process files with the following extensions
EXTENSIONS = {'.py', '.json', '.txt', '.md'}

def process_file(filepath: str) -> bool:
    """
    Reads a file, replaces occurrences of the outdated joint names with the new names,
    and writes the file back if any changes were made.
    
    Returns:
        True if the file has been updated, False otherwise.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Could not read '{filepath}': {e}")
        return False

    original_content = content
    for old_name, new_name in REPLACE_MAP.items():
        content = content.replace(old_name, new_name)

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {filepath}")
        return True
    return False

def update_directory(root_dir: str) -> None:
    """
    Recursively traverse the directory starting from `root_dir` to update files.
    """
    for subdir, dirs, files in os.walk(root_dir):
        for file in files:
            file_ext = os.path.splitext(file)[1]
            if file_ext in EXTENSIONS:
                filepath = os.path.join(subdir, file)
                process_file(filepath)

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Recursively update joint names within files in the directory."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Directory to search (default: current directory)"
    )
    args = parser.parse_args()
    update_directory(args.directory)

if __name__ == "__main__":
    main()