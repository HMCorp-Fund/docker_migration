import os
import zipfile
import tarfile
import shutil
import tempfile
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
    
    # Add extract-only related arguments
    parser.add_argument('--extract-only', action='store_true', 
                      help='Extract files without restoring Docker components')
    parser.add_argument('--target-dir', default='.',
                      help='Directory to extract application files to (for extract-only mode)')
    
    # Add backup-all argument
    parser.add_argument('--backup-all', action='store_true',
                      help='Backup all Docker resources on the server, not just those in docker-compose.yml')
    
    # Add additional-path argument
    parser.add_argument('--additional-path', 
                      help='Additional path to include in backup as a separate archive')
    
    args = parser.parse_args()
    
    compose_file = 'docker-compose.yml'
    
    if args.mode == 'backup':
        if os.path.exists(compose_file) and not args.backup_all:
            print(f"Found {compose_file}. Backing up resources defined in the compose file...")
            images, containers, networks, additional_files = parse_compose_file(compose_file)
            docker_backup_path = backup_docker_data(images, containers, networks)
            include_current_dir = True
        else:
            if args.backup_all:
                print("Backing up all Docker resources on the server...")
            else:
                print(f"No {compose_file} found. Backing up all running Docker entities...")
            
            docker_backup_path, images, containers, networks = backup_all_docker_data()
            additional_files = []
            
        # Handle current directory inclusion
        include_current_dir = False

        if args.additional_path:
            # When additional path is provided, don't automatically include current dir
            print(f"Using specified path {args.additional_path} for application files")
            include_current_dir = False
        elif not args.no_prompt:
            # Only prompt when no additional path AND prompts aren't disabled
            include_dir = input("Do you want to include the current directory in the backup? (yes/no): ")
            include_current_dir = include_dir.lower() == 'yes'

        # Handle additional path
        additional_path = None
        if args.additional_path:
            if os.path.exists(args.additional_path):
                print(f"Including additional path in backup: {args.additional_path}")
                additional_path = os.path.abspath(args.additional_path)
            else:
                print(f"Warning: Additional path does not exist: {args.additional_path}")

        # Create archives
        current_directory = os.getcwd()
        archive_path = create_archives(
            docker_backup_path, 
            current_directory if include_current_dir else None,
            additional_files,
            additional_path
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
        
        if args.extract_only:
            # Just extract files without Docker restoration
            extract_dir = args.target_dir if args.target_dir else '.'
            print(f"Extracting all files from backup to {extract_dir}...")
            
            # Extract the main archive
            temp_dir = tempfile.mkdtemp(prefix="docker_extract_")
            with tarfile.open(args.backup_file, 'r:*') as tar:
                tar.extractall(path=temp_dir)
            
            # Extract inner archives to target directory
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                if file.endswith('.tar') and tarfile.is_tarfile(file_path):
                    print(f"Extracting inner archive: {file}")
                    
                    # For additional_path archive, extract to a specific folder
                    if file.startswith("additional_path_"):
                        additional_extract_dir = os.path.join(extract_dir, "additional_path")
                        os.makedirs(additional_extract_dir, exist_ok=True)
                        with tarfile.open(file_path, 'r:*') as tar:
                            tar.extractall(path=additional_extract_dir)
                        print(f"Additional path files extracted to: {additional_extract_dir}")
                    else:
                        # Normal extraction for other archives
                        with tarfile.open(file_path, 'r:*') as tar:
                            tar.extractall(path=extract_dir)
            
            print(f"All files extracted to {extract_dir}")
            shutil.rmtree(temp_dir)
        else:
            # Normal restoration process
            restored_images, restored_networks, restored_containers = restore_docker_backup(args.backup_file)
        
        # Check if Docker services are running properly after restoration
        print("Checking if Docker services are running properly after restoration...")
        check_docker_services()

if __name__ == "__main__":
    main()