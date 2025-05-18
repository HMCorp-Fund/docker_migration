import os
import tarfile
import zipfile

def extract_archives(archive_path, destination):
    if archive_path.endswith('.tar.gz') or archive_path.endswith('.tgz'):
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(path=destination)
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

def main(archive_path):
    reinstall_docker(archive_path)
    check_docker_status()

if __name__ == "__main__":
    # Example usage: main('path_to_your_archive.tar.gz')
    pass  # This file is intended to be executed with an archive path as an argument.