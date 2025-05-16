import os
import tarfile
import tempfile
import datetime
import shutil
from docker_utils.compose_parser import parse_compose_file
from docker_utils.docker_backup import create_docker_backup

def create_archives(docker_backup_path, current_dir_path=None, additional_files=None):
    """
    Create archives for Docker backup and current directory
    
    Args:
        docker_backup_path (str): Path to the Docker backup directory
        current_dir_path (str, optional): Path to the current directory to include
        additional_files (list, optional): List of additional files to include
        
    Returns:
        str: Path to the created main archive
    """
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    archive_dir = tempfile.mkdtemp(prefix="docker_migration_")
    
    # Create Docker backup archive
    docker_archive = os.path.join(archive_dir, f'docker_backup_{timestamp}.tar.gz')
    print(f"Creating Docker backup archive: {docker_archive}")
    
    with tarfile.open(docker_archive, 'w:gz') as tar:
        tar.add(docker_backup_path, arcname=os.path.basename(docker_backup_path))
    
    files_to_archive = [docker_archive]
    
    # Create current directory archive if specified
    if current_dir_path:
        current_dir_archive = os.path.join(archive_dir, f'current_dir_{timestamp}.tar.gz')
        print(f"Creating current directory archive: {current_dir_archive}")
        
        with tarfile.open(current_dir_archive, 'w:gz') as tar:
            for item in os.listdir(current_dir_path):
                item_path = os.path.join(current_dir_path, item)
                # Skip the archive directory and Docker backup directory
                if item_path != archive_dir and item_path != docker_backup_path:
                    tar.add(item_path, arcname=os.path.basename(item_path))
        
        files_to_archive.append(current_dir_archive)
    
    # Add additional files if specified
    if additional_files and len(additional_files) > 0:
        additional_files_archive = os.path.join(archive_dir, f'additional_files_{timestamp}.tar.gz')
        print(f"Creating additional files archive: {additional_files_archive}")
        
        with tarfile.open(additional_files_archive, 'w:gz') as tar:
            for file_path in additional_files:
                if os.path.exists(file_path):
                    tar.add(file_path, arcname=os.path.basename(file_path))
        
        files_to_archive.append(additional_files_archive)
    
    # Create main archive containing all archives
    main_archive = os.path.join(os.getcwd(), f'docker_migration_{timestamp}.tar.gz')
    print(f"Creating main archive: {main_archive}")
    
    with tarfile.open(main_archive, 'w:gz') as tar:
        for file_path in files_to_archive:
            tar.add(file_path, arcname=os.path.basename(file_path))
        
        # Add a README file
        readme_path = os.path.join(archive_dir, 'README.txt')
        with open(readme_path, 'w') as f:
            f.write("Docker Migration Archive\n")
            f.write("======================\n\n")
            f.write(f"Created: {datetime.datetime.now()}\n\n")
            f.write("Contents:\n")
            for file_path in files_to_archive:
                f.write(f"- {os.path.basename(file_path)}\n")
        
        tar.add(readme_path, arcname=os.path.basename(readme_path))
    
    # Cleanup temporary archives
    shutil.rmtree(archive_dir)
    
    return main_archive

def prepare_docker_data(compose_file):
    docker_data = parse_compose_file(compose_file)
    backup_file = create_docker_backup(docker_data)
    return docker_data['images'], docker_data['containers'], docker_data['networks'], backup_file

def main(compose_file, include_current_dir=False):
    docker_images, docker_containers, docker_networks, backup_file = prepare_docker_data(compose_file)
    
    additional_files = docker_images + docker_containers + docker_networks
    current_dir_path = os.getcwd() if include_current_dir else None
    create_archives(backup_file, current_dir_path, additional_files)

if __name__ == "__main__":
    compose_file = "docker-compose.yml"  # Assuming the compose file is named this
    include_current_dir = True  # Change as needed
    main(compose_file, include_current_dir)