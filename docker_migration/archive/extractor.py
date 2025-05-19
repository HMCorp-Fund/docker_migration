import os
import tarfile
import zipfile
import glob
import tempfile

def extract_archives(archive_path, destination):
    if not destination:
        destination = os.getcwd()
        
    print(f"Extracting {archive_path} to {destination}")
    
    if archive_path.endswith('.tar.gz') or archive_path.endswith('.tgz'):
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(path=destination)
    elif archive_path.endswith('.tar'):  # ADD THIS LINE
        with tarfile.open(archive_path, 'r') as tar:  # ADD THIS LINE
            tar.extractall(path=destination)  # ADD THIS LINE
    elif archive_path.endswith('.zip'):
        with zipfile.ZipFile(archive_path, 'r') as zip_ref:
            zip_ref.extractall(destination)
    else:
        raise ValueError("Unsupported archive format")

def reinstall_docker(archive_path):
    # Extract the Docker backup and compose files
    extract_archives(archive_path, './__docker_backup')
    
    # Assuming the docker-compose.yml file is in the current directory
    os.system('docker-compose up -d')

def check_docker_status():
    # Check if the Docker services are running
    result = os.system('docker-compose ps')
    if result == 0:
        print("Docker services are running.")
    else:
        print("Docker services are not running.")

# Add this NEW function to properly handle additional files extraction
def extract_backup(backup_file, target_dir=None):
    """
    Extract backup file to target directory and automatically
    handle additional_files archives for source code restoration.
    
    Args:
        backup_file (str): Path to backup file
        target_dir (str, optional): Directory to extract to
        
    Returns:
        str: Path to extracted directory
    """
    if not target_dir:
        target_dir = os.getcwd()
    
    os.makedirs(target_dir, exist_ok=True)
    print(f"Extracting backup to {target_dir}...")
    
    # Extract the main backup
    extract_archives(backup_file, target_dir)
    
    # Find and extract any additional_files archives (source code)
    additional_files = glob.glob(os.path.join(target_dir, "additional_files_*.tar"))
    if additional_files:
        print(f"Found {len(additional_files)} additional files archives")
        for additional_file in additional_files:
            print(f"Extracting additional files from: {additional_file}")
            try:
                extract_archives(additional_file, target_dir)
                print(f"Successfully extracted source code from {additional_file}")
            except Exception as e:
                print(f"Error extracting additional files: {e}")
    else:
        print("No additional files archives found")
    
    return target_dir

def main(archive_path):
    reinstall_docker(archive_path)
    check_docker_status()

if __name__ == "__main__":
    # Example usage: main('path_to_your_archive.tar.gz')
    pass  # This file is intended to be executed with an archive path as an argument.