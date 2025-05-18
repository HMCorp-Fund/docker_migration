import os
import tarfile
import tempfile
import datetime
import shutil
from docker_migration.docker_utils.compose_parser import parse_compose_file
from docker_migration.docker_utils.docker_backup import create_docker_backup

def create_archives(docker_backup_path, current_dir=None, additional_files=[], docker_src_base_dir=None):
    """
    Create archive files for Docker backup and application directories
    
    Args:
        docker_backup_path (str): Path to the Docker backup directory
        current_dir (str, optional): Path to the current directory to include
        additional_files (list): List of additional files to include
        docker_src_base_dir (str, optional): Docker source base directory to include as a separate archive
        
    Returns:
        str: Path to the final archive file
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create a temporary directory to store all archives
    temp_dir = tempfile.mkdtemp(prefix="docker_migration_")
    
    # Archive Docker backup
    docker_archive = os.path.join(temp_dir, f"docker_backup_{timestamp}.tar")
    with tarfile.open(docker_archive, "w") as tar:
        tar.add(docker_backup_path, arcname=os.path.basename(docker_backup_path))
    
    # Archive current directory if specified
    if current_dir:
        current_dir_archive = os.path.join(temp_dir, f"current_dir_{timestamp}.tar")
        with tarfile.open(current_dir_archive, "w") as tar:
            for item in os.listdir(current_dir):
                # Skip the Docker backup directory and other common exclusions
                if item in [os.path.basename(docker_backup_path), '__pycache__', '.git', '.vscode', 'venv', 'env']:
                    continue
                    
                item_path = os.path.join(current_dir, item)
                tar.add(item_path, arcname=item)
    
    # Archive Docker source base directory if specified
    if docker_src_base_dir:
        docker_src_archive = os.path.join(temp_dir, f"docker_src_base_dir_{timestamp}.tar")
        path_basename = os.path.basename(docker_src_base_dir)
        
        with tarfile.open(docker_src_archive, "w") as tar:
            # Add the entire folder structure
            tar.add(docker_src_base_dir, arcname=path_basename)
        
        print(f"Docker source base directory archived: {docker_src_base_dir} -> {docker_src_archive}")
    
    # Archive additional files if any
    if additional_files:
        add_files_archive = os.path.join(temp_dir, f"additional_files_{timestamp}.tar")
        with tarfile.open(add_files_archive, "w") as tar:
            for file_path in additional_files:
                if os.path.exists(file_path):
                    tar.add(file_path, arcname=os.path.basename(file_path))
    
    # Create README
    readme_path = os.path.join(temp_dir, "README.txt")
    with open(readme_path, "w") as f:
        f.write("Docker Migration Backup\n")
        f.write("======================\n\n")
        f.write(f"Created on: {datetime.datetime.now()}\n\n")
        f.write("This archive contains Docker backup data and application files.\n")
        f.write("To restore, use the Docker Migration tool with --mode restore option.\n")
    
    # Create final archive containing all the above archives
    final_archive = f"docker_migration_{timestamp}.tar"
    with tarfile.open(final_archive, "w") as tar:
        for item in os.listdir(temp_dir):
            item_path = os.path.join(temp_dir, item)
            tar.add(item_path, arcname=item)
    
    # Clean up temporary files
    shutil.rmtree(temp_dir)
    shutil.rmtree(docker_backup_path)
    
    print(f"Created archive: {final_archive}")
    return final_archive

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