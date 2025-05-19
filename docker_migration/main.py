import os
import zipfile
import tarfile
import shutil
import tempfile
import argparse
import subprocess
import yaml
from docker_migration.docker_utils.compose_parser import parse_compose_file
from docker_migration.docker_utils.docker_backup import backup_docker_data, backup_all_docker_data, restore_docker_backup
from docker_migration.archive.archiver import create_archives
from docker_migration.validation.health_check import check_docker_services
from docker_migration.transfer.file_transfer import transfer_files

def run_command(cmd, capture_output=True):
    """Execute a shell command and optionally return its output"""
    if capture_output:
        return subprocess.check_output(cmd, shell=True, text=True).strip()
    else:
        subprocess.run(cmd, shell=True, check=True)

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
    parser.add_argument('--no-prompt', action='store_true', 
                        help='Do not prompt for user input (useful for scripted operations)')
    
    # Add extract-only related arguments
    parser.add_argument('--extract-only', action='store_true', 
                      help='Extract files without restoring Docker components')
    parser.add_argument('--target-dir', default='.',
                      help='Directory to extract application files to (for extract-only mode)')
    
    # Add backup-all argument
    parser.add_argument('--backup-all', action='store_true',
                      help='Backup all Docker resources on the server, not just those in docker-compose.yml')
    
    # Replace the additional-path argument with docker-src-base-dir
    parser.add_argument('--docker-src-base-dir', 
                      help='Docker source base directory to include in backup as a separate archive')
    # Legacy support for old parameter name
    parser.add_argument('--additional-path', dest='docker_src_base_dir',
                      help='DEPRECATED: Use --docker-src-base-dir instead')
    
    # Add a new argument in main.py
    parser.add_argument('--compose-file-path', 
                      help='Path to docker-compose.yml file (for restore mode)')
    
    # Add these arguments in the parser section
    parser.add_argument('--skip-images', action='store_true',
                      help='Skip backing up Docker images (which can be large)')
    parser.add_argument('--skip-containers', action='store_true',
                      help='Skip backing up Docker containers')
    parser.add_argument('--config-only', action='store_true',
                      help='Only backup configurations (skip images and containers)')
    
    # Add this to your argument parser
    parser.add_argument('--pull-images', action='store_true',
                      help='Pull Docker images defined in docker-compose.yml before backup')
    
    args = parser.parse_args()
    
    compose_file = 'docker-compose.yml'
    
    if args.mode == 'backup':
        if os.path.exists(compose_file) and not args.backup_all:
            print(f"Found {compose_file}. Backing up resources defined in the compose file...")
            images, containers, networks, volumes, additional_files = parse_compose_file(compose_file)
            
            # Debug output
            print("Resources detected in docker-compose.yml:")
            print(f"- Images: {', '.join(images)}")
            print(f"- Containers: {', '.join(containers)}")
            print(f"- Networks: {', '.join(networks)}")
            print(f"- Volumes: {', '.join(volumes)}")
            
            # Pull images if requested
            if args.pull_images and images:
                print("Pulling Docker images defined in docker-compose.yml...")
                for image in images:
                    print(f"Pulling image: {image}")
                    run_command(f"docker pull {image}", capture_output=False)
            
            # Apply skip flags
            if args.config_only or args.skip_images:
                print("Skipping Docker images as requested")
                images = []
            
            if args.config_only or args.skip_containers:
                print("Skipping Docker containers as requested")
                containers = []
            
            docker_backup_path = backup_docker_data(
                backup_dir=None,  # Let the function create a timestamped directory
                images=images,
                containers=containers,
                networks=networks,
                volumes=volumes
            )
            include_current_dir = True
        else:
            if args.backup_all:
                print("Backing up all Docker resources on the server...")
            else:
                print(f"No {compose_file} found. Backing up all running Docker entities...")
            
            # Pass skip flags to backup_all_docker_data
            skip_images = args.config_only or args.skip_images
            skip_containers = args.config_only or args.skip_containers
            
            docker_backup_path, images, containers, networks = backup_all_docker_data(
                skip_images=skip_images,
                skip_containers=skip_containers
            )
            additional_files = []
            
        # Handle current directory inclusion
        include_current_dir = False

        # Update variable references in main.py
        if args.docker_src_base_dir:
            # When docker source base directory is provided, don't automatically include current dir
            print(f"Using specified path {args.docker_src_base_dir} for Docker source files")
            include_current_dir = False
        elif not args.no_prompt:
            include_dir = input("Do you want to include the current directory in the backup? (yes/no): ")
            include_current_dir = include_dir.lower() == 'yes'

        # Handle docker source base directory
        docker_src_base_dir = None
        if args.docker_src_base_dir:
            if os.path.exists(args.docker_src_base_dir):
                print(f"Including Docker source base directory in backup: {args.docker_src_base_dir}")
                docker_src_base_dir = os.path.abspath(args.docker_src_base_dir)
            else:
                print(f"Warning: Docker source base directory does not exist: {args.docker_src_base_dir}")

        # Create archives
        current_directory = os.getcwd()
        archive_path = create_archives(
            docker_backup_path, 
            current_directory if include_current_dir else None,
            additional_files,
            docker_src_base_dir
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
                    
                    # For Docker source base directory archive, extract to a specific folder  
                    if file.startswith("additional_path_") or file.startswith("docker_src_base_dir_"):
                        docker_src_extract_dir = os.path.join(extract_dir, "docker_src_base_dir")
                        os.makedirs(docker_src_extract_dir, exist_ok=True)
                        with tarfile.open(file_path, 'r:*') as tar:
                            tar.extractall(path=docker_src_extract_dir)
                        print(f"Docker source base directory files extracted to: {docker_src_extract_dir}")
            
            print(f"All files extracted to {extract_dir}")
            shutil.rmtree(temp_dir)
        else:
            # Normal restoration process
            compose_file_path = args.compose_file_path
            
            # If no compose file is specified but we extracted an additional path,
            # automatically check for docker-compose.yml in the additional_path directory
            if not compose_file_path and os.path.exists("additional_path"):
                potential_compose_file = os.path.join("additional_path", "docker-compose.yml")
                if os.path.exists(potential_compose_file):
                    print(f"Found docker-compose.yml in additional_path: {potential_compose_file}")
                    compose_file_path = potential_compose_file
            
            # If no compose file is specified but we extracted a Docker source base directory,
            # automatically check for docker-compose.yml in that directory
            if not compose_file_path and os.path.exists("docker_src_base_dir"):
                potential_compose_file = os.path.join("docker_src_base_dir", "docker-compose.yml")
                if os.path.exists(potential_compose_file):
                    print(f"Found docker-compose.yml in Docker source base directory: {potential_compose_file}")
                    compose_file_path = potential_compose_file
            
            # If no compose file found yet, check the first directory inside docker_src_base_dir
            if not compose_file_path and os.path.exists("docker_src_base_dir"):
                # List items in docker_src_base_dir
                items = os.listdir("docker_src_base_dir")
                
                # Filter for directories only
                subdirs = [item for item in items if os.path.isdir(os.path.join("docker_src_base_dir", item))]
                
                # If subdirectories exist, check the first one for docker-compose.yml
                if subdirs:
                    first_subdir = subdirs[0]
                    nested_compose_path = os.path.join("docker_src_base_dir", first_subdir, "docker-compose.yml")
                    
                    if os.path.exists(nested_compose_path):
                        print(f"Found docker-compose.yml in first subdirectory: {nested_compose_path}")
                        compose_file_path = nested_compose_path
                    else:
                        print(f"No docker-compose.yml found in {first_subdir} directory")
            
            restored_images, restored_networks, restored_containers = restore_docker_backup(
                args.backup_file, 
                compose_file_path=compose_file_path
            )
            
            # Wait a moment for services to start
            print("Waiting for services to start...")
            import time
            time.sleep(5)
            
            # Check if Docker services are running properly after restoration
            print("Checking if Docker services are running properly after restoration...")
            check_docker_services()

def restore_mode(args):
    """Handle restore mode"""
    # Ensure target_dir exists and is valid
    if args.target_dir:
        os.makedirs(args.target_dir, exist_ok=True)
        target_dir = args.target_dir
    else:
        target_dir = os.getcwd()
    
    print(f"Restoring to directory: {target_dir}")
    
    # Extract the backup
    from docker_migration.archive.extractor import extract_backup
    extract_dir = extract_backup(args.backup_file, target_dir)
    
    # Rest of your restore code...

def load_config(config_path="~/.docker-migration.conf"):
    """Load configuration file"""
    config_path = os.path.expanduser(config_path)
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return {}

if __name__ == "__main__":
    main()