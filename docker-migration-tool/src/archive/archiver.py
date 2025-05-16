import os
import tarfile
import zipfile
import subprocess
from docker_utils.compose_parser import parse_compose_file
from docker_utils.docker_backup import create_docker_backup

def create_archive(archive_name, docker_data, include_current_dir=False):
    with tarfile.open(archive_name, "w:gz") as tar:
        for item in docker_data:
            tar.add(item, arcname=os.path.basename(item))
        
        if include_current_dir:
            for root, dirs, files in os.walk('.'):
                for file in files:
                    tar.add(os.path.join(root, file), arcname=os.path.relpath(os.path.join(root, file)))

def prepare_docker_data(compose_file):
    docker_data = parse_compose_file(compose_file)
    backup_file = create_docker_backup(docker_data)
    return docker_data['images'], docker_data['containers'], docker_data['networks'], backup_file

def main(compose_file, include_current_dir=False):
    docker_images, docker_containers, docker_networks, backup_file = prepare_docker_data(compose_file)
    
    archive_name = "docker_migration.tar.gz"
    create_archive(archive_name, [backup_file] + docker_images + docker_containers + docker_networks, include_current_dir)

if __name__ == "__main__":
    compose_file = "docker-compose.yml"  # Assuming the compose file is named this
    include_current_dir = True  # Change as needed
    main(compose_file, include_current_dir)