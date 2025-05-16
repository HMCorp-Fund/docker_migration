import os
import zipfile
import tarfile
import shutil
from docker_utils.compose_parser import parse_compose_file
from docker_utils.docker_backup import backup_docker_data, backup_all_docker_data
from archive.archiver import create_archives
from transfer.file_transfer import transfer_files
from validation.health_check import check_docker_services

def main():
    # Check if docker-compose.yml exists
    compose_file = 'docker-compose.yml'
    
    if os.path.exists(compose_file):
        print(f"Found {compose_file}. Backing up resources defined in the compose file...")
        # Step 1: Parse the Docker Compose file to identify related resources
        images, containers, networks, additional_files = parse_compose_file(compose_file)
        
        # Step 2: Backup Docker data
        docker_backup_path = backup_docker_data(images, containers, networks)
        
        # For compose-based migration, include the current directory
        include_current_dir = True
    else:
        print(f"No {compose_file} found. Backing up all running Docker entities...")
        # Backup all running Docker entities
        docker_backup_path, images, containers, networks = backup_all_docker_data()
        additional_files = []
        
        # For non-compose migration, ask if user wants to include current directory
        include_dir = input("Do you want to include the current directory in the backup? (yes/no): ")
        include_current_dir = include_dir.lower() == 'yes'

    # Step 3: Create archives
    current_directory = os.getcwd()
    archive_path = create_archives(docker_backup_path, current_directory if include_current_dir else None, additional_files)

    # Step 4: Transfer files to the new server (if option chosen)
    transfer_option = input("Do you want to transfer the files to the new server? (yes/no): ")
    if transfer_option.lower() == 'yes':
        new_server_path = input("Enter the path on the new server (use ~ for home): ")
        transfer_files(archive_path, new_server_path)

    # Step 5: Reinstall Docker on the new server (this would typically be done via SSH)
    # For demonstration, we assume the extraction and installation is handled on the new server
    print("Please extract the archives on the new server and run the installation script.")

    # Step 6: Check if Docker services are running
    check_docker_services()

if __name__ == "__main__":
    main()