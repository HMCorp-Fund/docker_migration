import os
import tarfile
import tempfile
import datetime
import shutil
import subprocess
import time
from docker_migration.docker_utils.compose_parser import parse_compose_file
from docker_migration.docker_utils.docker_backup import create_docker_backup
from humanize import naturalsize # type: ignore

def create_archives(docker_backup_path, current_dir=None, additional_files=[], docker_src_base_dir=None, 
                   compression='balanced'):
    """
    Create archive files for Docker backup and application directories with optimized performance
    
    Args:
        docker_backup_path (str): Path to the Docker backup directory
        current_dir (str, optional): Path to the current directory to include
        additional_files (list): List of additional files to include
        docker_src_base_dir (str, optional): Docker source base directory
        compression (str): Compression level: none, fast, balanced, max
        
    Returns:
        str: Path to the final archive file
    """
    start_time = time.time()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    final_archive = f"docker_migration_{timestamp}.tar"
    
    # Set compression mode based on parameter
    if compression == 'none':
        mode = 'w'  # No compression, fastest
    elif compression == 'fast':
        mode = 'w:gz'  # gzip with default compression (medium)
    elif compression == 'max':
        mode = 'w:bz2'  # bzip2 compression (slower but better compression)
    else:  # 'balanced'
        mode = 'w:gz'  # Default to gzip
    
    # Use a progress indicator
    print("Creating final archive... This may take a few minutes.")
    
    # Common exclusion patterns
    exclusions = ['__pycache__', '.git', '.vscode', 'venv', 'env', 'node_modules', '*.pyc']
    
    # Create README file directly in the backup directory for inclusion
    readme_path = os.path.join(docker_backup_path, "README.txt")
    with open(readme_path, "w") as f:
        f.write("Docker Migration Backup\n")
        f.write("======================\n\n")
        f.write(f"Created on: {datetime.datetime.now()}\n\n")
        f.write("This archive contains Docker backup data and application files.\n")
        f.write("To restore, use the Docker Migration tool with --mode restore option.\n")
    
    # Create single archive directly
    with tarfile.open(final_archive, mode) as tar:
        # Add docker backup directory (this already contains images, containers, networks, volumes)
        print(f"Adding Docker backup data from: {docker_backup_path}")
        tar.add(docker_backup_path, arcname=os.path.basename(docker_backup_path))
        
        # Add current directory if specified
        if current_dir:
            print(f"Adding current directory: {current_dir}")
            for item in os.listdir(current_dir):
                # Skip exclusions
                if any(pattern in item for pattern in exclusions) or \
                   item == os.path.basename(docker_backup_path) or \
                   item == os.path.basename(final_archive):
                    continue
                    
                item_path = os.path.join(current_dir, item)
                # Show progress for large directories
                print(f"  Adding: {item}")
                tar.add(item_path, arcname=f"current_dir/{item}", recursive=True)
        
        # Add Docker source base directory if specified
        if docker_src_base_dir:
            print(f"Adding Docker source base directory: {docker_src_base_dir}")
            path_basename = os.path.basename(docker_src_base_dir)
            tar.add(docker_src_base_dir, arcname=f"docker_src_base_dir/{path_basename}", recursive=True)
        
        # Add additional files if any
        if additional_files:
            print(f"Adding {len(additional_files)} additional files")
            for file_path in additional_files:
                if os.path.exists(file_path):
                    tar.add(file_path, arcname=f"additional_files/{os.path.basename(file_path)}")
    
    # Clean up temporary files
    shutil.rmtree(docker_backup_path)
    
    elapsed_time = time.time() - start_time
    archive_size = os.path.getsize(final_archive)
    print(f"Created archive: {final_archive} in {elapsed_time:.1f} seconds ({naturalsize(archive_size)})")
    return final_archive

def create_archives_fast(docker_backup_path, current_dir=None, additional_files=[], docker_src_base_dir=None, 
                       compression='balanced'):
    """Ultra-fast archive creation using system tar command"""
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    final_archive = f"docker_migration_{timestamp}.tar"
    
    # Define compression option
    if compression == 'none':
        comp_opt = ""  # No compression
    elif compression == 'fast':
        comp_opt = "--gzip"  # gzip (-z)
    elif compression == 'max':
        comp_opt = "--bzip2"  # bzip2 (-j)
    else:  # 'balanced'
        comp_opt = "--gzip"
    
    # Create the file list to archive
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as file_list:
        # Add docker backup directory
        file_list.write(f"{docker_backup_path}\n")
        
        # Add current directory if specified
        if current_dir:
            file_list.write(f"{current_dir}\n")
        
        # Add Docker source base directory
        if docker_src_base_dir:
            file_list.write(f"{docker_src_base_dir}\n")
        
        # Add additional files
        for file_path in additional_files:
            if os.path.exists(file_path):
                file_list.write(f"{file_path}\n")
    
    try:
        # Create the archive using system tar
        exclusions = ['--exclude=__pycache__', '--exclude=.git', '--exclude=.vscode', 
                    '--exclude=venv', '--exclude=env', '--exclude=node_modules', 
                    '--exclude=*.pyc', f'--exclude={final_archive}']
        
        cmd = ["tar", "-cf", final_archive]
        if comp_opt:
            cmd.append(comp_opt)
        cmd.extend(exclusions)
        cmd.extend(["-T", file_list.name])
        
        print(f"Creating archive with system tar: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        
        print(f"Created archive: {final_archive}")
        return final_archive
    finally:
        # Clean up
        os.unlink(file_list.name)
        shutil.rmtree(docker_backup_path)

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