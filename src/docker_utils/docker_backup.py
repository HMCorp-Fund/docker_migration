import os
import docker # type: ignore
import json
import tempfile
import tarfile
import shutil
import subprocess
import io
import datetime


def backup_docker_data(images, containers, networks):
    """
    Backup specified Docker data
    
    Args:
        images (list): List of image names to backup
        containers (list): List of container IDs to backup
        networks (list): List of network IDs to backup
        
    Returns:
        str: Path to the Docker backup directory
    """
    client = docker.from_env()
    
    # Create a backup directory
    backup_dir = tempfile.mkdtemp(prefix="docker_backup_")
    
    # Save container details
    with open(os.path.join(backup_dir, 'containers.json'), 'w') as f:
        container_data = []
        for container_id in containers:
            try:
                container = client.containers.get(container_id)
                container_data.append({
                    'id': container.id,
                    'name': container.name,
                    'image': container.image.tags[0] if container.image.tags else container.image.id,
                    'command': container.attrs['Config']['Cmd'],
                    'ports': container.attrs['HostConfig']['PortBindings'] if 'PortBindings' in container.attrs['HostConfig'] else {},
                    'volumes': container.attrs['HostConfig']['Binds'] if 'Binds' in container.attrs['HostConfig'] else [],
                    'environment': container.attrs['Config']['Env'] if 'Env' in container.attrs['Config'] else [],
                    'labels': container.attrs['Config']['Labels'] if 'Labels' in container.attrs['Config'] else {},
                    'restart_policy': container.attrs['HostConfig']['RestartPolicy'] if 'RestartPolicy' in container.attrs['HostConfig'] else {},
                })
            except docker.errors.NotFound:
                print(f"Warning: Container {container_id} not found, skipping")
                
        json.dump(container_data, f, indent=2)
    
    # Save images
    os.makedirs(os.path.join(backup_dir, 'images'), exist_ok=True)
    for image_name in images:
        try:
            print(f"Saving image: {image_name}")
            image_filename = os.path.join(backup_dir, 'images', image_name.replace('/', '_').replace(':', '_') + '.tar')
            
            # Use docker CLI for more reliable image saving
            subprocess.run(['docker', 'save', '-o', image_filename, image_name], check=True)
            
        except (docker.errors.ImageNotFound, subprocess.SubprocessError) as e:
            print(f"Error saving image {image_name}: {e}")
    
    # Save networks
    os.makedirs(os.path.join(backup_dir, 'networks'), exist_ok=True)
    for network_name in networks:
        try:
            network = client.networks.get(network_name)
            network_filename = os.path.join(backup_dir, 'networks', network_name + '.json')
            with open(network_filename, 'w') as f:
                json.dump(network.attrs, f, indent=2)
        except docker.errors.NotFound:
            print(f"Warning: Network {network_name} not found, skipping")
    
    # Create a manifest file with metadata
    with open(os.path.join(backup_dir, 'manifest.json'), 'w') as f:
        json.dump({
            'images': images,
            'containers': containers,
            'networks': networks,
            'date': str(datetime.datetime.now()),
            'docker_version': client.version()
        }, f, indent=2)
    
    return backup_dir


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
    containers = client.containers.list(all=True)
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
    
    # Create backup with the collected resources
    backup_dir = backup_docker_data(images, container_ids, networks)
    
    return backup_dir, images, container_ids, networks


def create_docker_backup(backup_dir, include_current_dir=False):
    """
    Legacy function - creates a single archive of Docker resources
    
    Args:
        backup_dir (str): Directory to store the backup
        include_current_dir (bool): Whether to include current directory in backup
        
    Returns:
        str: Path to the created backup file
    """
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
        # Create temp files for Docker resources
        temp_dir = tempfile.mkdtemp()
        
        # Save images info
        images_file = os.path.join(temp_dir, 'images.json')
        with open(images_file, 'w') as f:
            image_data = []
            for image in images:
                image_data.append({
                    'id': image.id,
                    'tags': image.tags,
                    'short_id': image.short_id,
                    'created': str(image.attrs.get('Created', '')),
                    'size': image.attrs.get('Size', 0)
                })
            json.dump(image_data, f, indent=2)
        tar.add(images_file, arcname='images.json')
        
        # Save containers info
        containers_file = os.path.join(temp_dir, 'containers.json')
        with open(containers_file, 'w') as f:
            container_data = []
            for container in containers:
                container_data.append({
                    'id': container.id,
                    'name': container.name,
                    'image': container.image.tags[0] if container.image.tags else container.image.id,
                    'status': container.status,
                    'ports': container.ports
                })
            json.dump(container_data, f, indent=2)
        tar.add(containers_file, arcname='containers.json')
        
        # Save networks info
        networks_file = os.path.join(temp_dir, 'networks.json')
        with open(networks_file, 'w') as f:
            network_data = []
            for network in networks:
                network_data.append({
                    'id': network.id,
                    'name': network.name,
                    'scope': network.attrs.get('Scope', ''),
                    'driver': network.attrs.get('Driver', '')
                })
            json.dump(network_data, f, indent=2)
        tar.add(networks_file, arcname='networks.json')

        # Include current directory files if specified
        if include_current_dir:
            current_dir = os.getcwd()
            for item in os.listdir(current_dir):
                itempath = os.path.join(current_dir, item)
                if os.path.isfile(itempath):
                    tar.add(itempath, arcname=item)
                elif os.path.isdir(itempath) and item != backup_dir:
                    tar.add(itempath, arcname=item)
        
        # Cleanup temp files
        shutil.rmtree(temp_dir)

    return backup_file


def transfer_backup(backup_file, destination):
    """
    Transfer the backup file to the destination
    
    Args:
        backup_file (str): Path to the backup file
        destination (str): Destination path
    """
    try:
        if ':' in destination:  # Remote destination with SCP
            user_host, remote_path = destination.split(':', 1)
            print(f"Transferring backup to {user_host}:{remote_path}...")
            subprocess.run(['scp', backup_file, destination], check=True)
        else:  # Local destination with copy
            print(f"Copying backup to {destination}...")
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            shutil.copy(backup_file, destination)
        print(f"Backup successfully transferred to {destination}")
    except (subprocess.SubprocessError, OSError) as e:
        print(f"Error transferring backup: {e}")


def main():
    backup_dir = './__docker_backup'
    backup_file = create_docker_backup(backup_dir, include_current_dir=True)
    transfer_backup(backup_file, '~/docker_backups')


if __name__ == "__main__":
    main()