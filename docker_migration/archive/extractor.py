import os
import tarfile
import zipfile
import glob
import logging

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

def extract_backup(backup_file, target_dir=None):
    extract_archives(backup_file, target_dir)
    
    # Add this code to also extract any additional_files archives
    additional_files_archives = glob.glob(os.path.join(target_dir, "additional_files_*.tar"))
    for archive_path in additional_files_archives:
        logging.info(f"Extracting additional files from: {archive_path}")
        try:
            with tarfile.open(archive_path, 'r') as tar:
                tar.extractall(path=target_dir)
        except Exception as e:
            logging.error(f"Error extracting additional files: {e}")
            # Don't fail the whole restoration process if this fails

def main(archive_path):
    reinstall_docker(archive_path)
    check_docker_status()

if __name__ == "__main__":
    # Example usage: main('path_to_your_archive.tar.gz')
    pass  # This file is intended to be executed with an archive path as an argument.