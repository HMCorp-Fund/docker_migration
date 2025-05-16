import os
import docker
import json
import tempfile
import tarfile
import shutil


def create_docker_backup(backup_dir, include_current_dir=False):
    client = docker.from_env()

    # Create a directory for the backup if it doesn't exist
    os.makedirs(backup_dir, exist_ok=True)

    # Identify Docker images, containers, and networks
    images = client.images.list()
    containers = client.containers.list(all=True)
    networks = client.networks.list()

    # Create a tar file for the backup
    backup_file = os.path.join(backup_dir, 'docker_backup.tar.gz')
    with tarfile.open(backup_file, 'w:gz') as tar:
        # Backup images
        for image in images:
            image_name = image.tags[0] if image.tags else 'untagged_image'
            tar.add(image_name)

        # Backup containers
        for container in containers:
            tar.add(container.name)

        # Backup networks
        for network in networks:
            tar.add(network.name)

        # Include current directory files if specified
        if include_current_dir:
            current_dir = os.getcwd()
            tar.add(current_dir, arcname=os.path.basename(current_dir))

    return backup_file


def transfer_backup(backup_file, destination):
    # Transfer the backup file to the new server
    shutil.copy(backup_file, destination)


def backup_all_docker_data():
    """
    Backup all running Docker entities (containers, images, networks)
    
    Returns:
        str: Path to the Docker backup directory
        list: List of image names
        list: List of container IDs
        list: List of network IDs
    """
    client = docker.from_env()
    
    # Get all running containers
    containers = client.containers.list()
    container_ids = [container.id for container in containers]
    
    # Get all images used by those containers
    images = []
    for container in containers:
        image = container.image
        if image.tags:
            images.append(image.tags[0])
        else:
            images.append(image.id)
    
    # Get all networks used by those containers
    networks = []
    for container in containers:
        container_networks = container.attrs['NetworkSettings']['Networks'].keys()
        networks.extend(container_networks)
    
    # Remove duplicates
    images = list(set(images))
    networks = list(set(networks))
    
    # Create a backup directory
    backup_dir = tempfile.mkdtemp(prefix="docker_backup_")
    
    # Save container details, image details and network details to files
    with open(os.path.join(backup_dir, 'containers.json'), 'w') as f:
        container_data = []
        for container_id in container_ids:
            container = client.containers.get(container_id)
            container_data.append({
                'id': container.id,
                'name': container.name,
                'image': container.image.tags[0] if container.image.tags else container.image.id,
                'command': container.attrs['Config']['Cmd'],
                'ports': container.attrs['HostConfig']['PortBindings'] if 'PortBindings' in container.attrs['HostConfig'] else {},
                'volumes': container.attrs['HostConfig']['Binds'] if 'Binds' in container.attrs['HostConfig'] else [],
                'environment': container.attrs['Config']['Env'] if 'Env' in container.attrs['Config'] else []
            })
        json.dump(container_data, f, indent=2)
    
    # Save images
    for image in images:
        # Save image logic here
        pass
        
    # Save networks
    for network in networks:
        # Save network logic here
        pass
    
    return backup_dir, images, container_ids, networks


def main():
    backup_dir = './__docker_backup'
    backup_file = create_docker_backup(backup_dir, include_current_dir=True)
    transfer_backup(backup_file, '~/docker_backups')


if __name__ == "__main__":
    main()