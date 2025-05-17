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
    
    # Add FTP-related arguments
    parser.add_argument('--transfer', action='store_true', help='Transfer the backup to another location')
    parser.add_argument('--destination', help='Destination path (local path, user@host:/path for SCP, or ftp://user:pass@host/path for FTP)')
    parser.add_argument('--ftp-user', help='FTP username (if not specified in destination)')
    parser.add_argument('--ftp-pass', help='FTP password (if not specified in destination)')
    parser.add_argument('--no-prompt', action='store_true', help='Do not prompt for user input')
    
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
            
            if args.no_prompt:
                include_current_dir = False
            else:
                include_dir = input("Do you want to include the current directory in the backup? (yes/no): ")
                include_current_dir = include_dir.lower() == 'yes'

        # Create archives
        current_directory = os.getcwd()
        archive_path = create_archives(
            docker_backup_path, 
            current_directory if include_current_dir else None, 
            additional_files
        )

        # Handle file transfer
        should_transfer = False
        destination = None
        
        if args.transfer and args.destination:
            should_transfer = True
            destination = args.destination
        elif not args.no_prompt:
            transfer_option = input("Do you want to transfer the files to the new server? (yes/no): ")
            if transfer_option.lower() == 'yes':
                destination = input("Enter destination path (user@host:/path for remote, or local path): ")
                should_transfer = True
        
        if should_transfer and destination:
            # If FTP destination, check for additional credentials
            if destination.startswith('ftp://') and args.ftp_user:
                # If the destination doesn't already have credentials, add them
                if '@' not in destination[6:]:
                    ftp_host_path = destination[6:]  # Remove 'ftp://'
                    password = args.ftp_pass if args.ftp_pass else ''
                    destination = f"ftp://{args.ftp_user}:{password}@{ftp_host_path}"
            
            transfer_files(archive_path, destination)

        print("Please extract the archives on the new server and run the installation script.")
    
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