import os
import zipfile
import tarfile
import shutil
import argparse
from docker_utils.compose_parser import parse_compose_file
from docker_utils.docker_backup import backup_docker_data, backup_all_docker_data, restore_docker_backup
from archive.archiver import create_archives
from transfer.file_transfer import transfer_files
from validation.health_check import check_docker_services

def main():
    parser = argparse.ArgumentParser(description='Docker Migration Tool')
    parser.add_argument('--mode', choices=['backup', 'restore'], default='backup',
                      help='Mode to run: backup or restore')
    parser.add_argument('--backup-file', help='Path to backup file (for restore mode)')
    
    args = parser.parse_args()
    
    compose_file = 'docker-compose.yml'
    
    if args.mode == 'backup':
        if os.path.exists(compose_file):
            print(f"Found {compose_file}. Backing up resources defined in the compose file...")
            images, containers, networks, additional_files = parse_compose_file(compose_file)
            docker_backup_path = backup_docker_data(images, containers, networks)
            include_current_dir = True
        else:
            print(f"No {compose_file} found. Backing up all running Docker entities...")
            docker_backup_path, images, containers, networks = backup_all_docker_data()
            additional_files = []
            include_dir = input("Do you want to include the current directory in the backup? (yes/no): ")
            include_current_dir = include_dir.lower() == 'yes'

        # Create archives
        current_directory = os.getcwd()
        archive_path = create_archives(
            docker_backup_path, 
            current_directory if include_current_dir else None, 
            additional_files
        )

        # Transfer files
        transfer_option = input("Do you want to transfer the files to the new server? (yes/no): ")
        if transfer_option.lower() == 'yes':
            destination = input("Enter destination path (user@host:/path for remote, or local path): ")
            transfer_files(archive_path, destination)

        print("Please extract the archives on the new server and run the installation script.")
        
        # Check if Docker services are running properly
        check_docker_services()
    
    elif args.mode == 'restore':
        if not args.backup_file:
            print("Error: --backup-file is required for restore mode")
            parser.print_help()
            return
            
        # Call the restore function
        restore_docker_backup(args.backup_file)
        
        # Check if Docker services are running properly after restoration
        print("Checking if Docker services are running properly after restoration...")
        check_docker_services()

if __name__ == "__main__":
    main()