import os
import json
import tempfile
import tarfile
import shutil
import subprocess
import datetime


def run_command(cmd, capture_output=True, use_sudo=True):
    """Run a shell command and return the output"""
    try:
        # Add sudo if required for any command when use_sudo is True
        if use_sudo:
            # Don't add sudo if it's already there
            if not cmd.strip().startswith("sudo "):
                cmd = f"sudo {cmd}"
            
        result = subprocess.run(cmd, shell=True, check=True, 
                              text=True, capture_output=capture_output)
        return result.stdout.strip() if capture_output else True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}")
        print(f"Error: {e}")
        if capture_output and hasattr(e, 'stderr'):
            print(f"STDERR: {e.stderr}")
        return None


def backup_docker_data(images=None, containers=None, networks=None, volumes=None):
    """
    Backup Docker data using CLI commands
    
    Args:
        images (list, optional): List of image names to backup
        containers (list, optional): List of container names to backup
        networks (list, optional): List of network names to backup
        volumes (list, optional): List of volume names to backup
        
    Returns:
        str: Path to the Docker backup directory
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = tempfile.mkdtemp(prefix="docker_backup_")
    
    # Create directories for each backup type
    images_dir = os.path.join(backup_dir, "images")
    containers_dir = os.path.join(backup_dir, "containers")
    networks_dir = os.path.join(backup_dir, "networks")
    volumes_dir = os.path.join(backup_dir, "volumes")
    
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(containers_dir, exist_ok=True)
    os.makedirs(networks_dir, exist_ok=True)
    os.makedirs(volumes_dir, exist_ok=True)
    
    # Backup images
    if images:
        for image in images:
            print(f"Saving image: {image}")
            image_file = os.path.join(images_dir, image.replace('/', '_').replace(':', '_') + '.tar')
            run_command(f"docker save {image} -o '{image_file}'")
    
    # Backup container configurations
    if containers:
        for container in containers:
            try:
                # Check if container exists before trying to inspect it
                check_result = run_command(f"docker ps -a --format '{{{{.Names}}}}' --filter name=^{container}$")
                if not check_result or container not in check_result:
                    print(f"Container {container} not found, skipping backup")
                    continue
                    
                print(f"Backing up container configuration: {container}")
                container_file = os.path.join(containers_dir, container + '.json')
                config = run_command(f"docker inspect {container}")
                
                if config:
                    with open(container_file, 'w') as f:
                        f.write(config)
            except Exception as e:
                print(f"Error backing up container {container}: {e}")
    
    # Backup networks
    if networks:
        for network in networks:
            try:
                # Check if network exists
                check_result = run_command(f"docker network ls --format '{{{{.Name}}}}' --filter name=^{network}$")
                if not check_result or network not in check_result:
                    print(f"Network {network} not found, skipping backup")
                    continue
                    
                print(f"Saved network configuration for: {network}")
                network_file = os.path.join(networks_dir, network + '.json')
                config = run_command(f"docker network inspect {network}")
                
                if config:
                    with open(network_file, 'w') as f:
                        f.write(config)
            except Exception as e:
                print(f"Error backing up network {network}: {e}")
    
    # Backup volumes
    if volumes:
        for volume in volumes:
            try:
                # Check if volume exists
                check_result = run_command(f"docker volume ls --format '{{{{.Name}}}}' --filter name=^{volume}$")
                if not check_result or volume not in check_result:
                    print(f"Volume {volume} not found, skipping backup")
                    continue
                    
                print(f"Backing up volume: {volume}")
                volume_dir = os.path.join(volumes_dir, volume)
                os.makedirs(volume_dir, exist_ok=True)
                
                # Use a temporary container to copy data from the volume
                temp_container = f"volume_backup_{timestamp}_{volume.replace('-', '_')}"
                run_command(f"docker run --rm -d --name {temp_container} -v {volume}:/data alpine sleep 60")
                
                # Create a tarball of the volume data
                volume_file = os.path.join(volume_dir, 'data.tar')
                run_command(f"docker exec {temp_container} tar -cf - -C /data . > {volume_file}")
                
                # Stop and remove the temp container
                run_command(f"docker stop {temp_container}")
                
                print(f"Volume {volume} data backed up successfully")
            except Exception as e:
                print(f"Error backing up volume {volume}: {e}")
                continue
    
    return backup_dir


def backup_all_docker_data():
    """
    Backup all Docker data using CLI commands
    
    Returns:
        str: Path to the Docker backup directory
        list: List of image names
        list: List of container IDs
        list: List of network IDs
    """
    # Get all containers (running and stopped)
    containers_raw = run_command("docker ps -a --format '{{.ID}}'")
    containers = containers_raw.splitlines() if containers_raw else []
    
    # Get all images, not just those used by containers
    images_raw = run_command("docker images --format '{{.Repository}}:{{.Tag}}'")
    images = []
    if images_raw:
        for img in images_raw.splitlines():
            if img != '<none>:<none>':  # Skip untagged images
                images.append(img)
    
    # Get images used by containers too (as backup)
    for container in containers:
        image = run_command(f"docker inspect --format='{{{{.Config.Image}}}}' {container}")
        if image and image not in images:
            images.append(image)
    
    # Get all networks
    networks_raw = run_command("docker network ls --format '{{.Name}}'")
    networks = networks_raw.splitlines() if networks_raw else []
    networks = [n for n in networks if n not in ('bridge', 'host', 'none')]
    
    # Create backup
    backup_dir = backup_docker_data(images, containers, networks)
    
    return backup_dir, images, containers, networks


def create_docker_backup(backup_dir, include_current_dir=False):
    """
    Legacy function - creates a single archive of Docker resources
    
    Args:
        backup_dir (str): Directory to store the backup
        include_current_dir (bool): Whether to include current directory in backup
        
    Returns:
        str: Path to the created backup file
    """
    client = docker.from_env() # type: ignore

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


def extract_backup(backup_file, extract_dir=None):
    """
    Extract a Docker backup archive
    
    Args:
        backup_file (str): Path to the backup file
        extract_dir (str, optional): Directory to extract to (default: creates temp dir)
        
    Returns:
        str: Path to the extracted backup directory
    """
    if not extract_dir:
        extract_dir = tempfile.mkdtemp(prefix="docker_restore_")
    
    print(f"Extracting backup {backup_file} to {extract_dir}...")
    
    # Check if it's a tarfile
    if tarfile.is_tarfile(backup_file):
        with tarfile.open(backup_file, 'r:*') as tar:
            tar.extractall(path=extract_dir)
    else:
        raise ValueError(f"File {backup_file} is not a valid tar archive")
    
    # Look for inner Docker backup archive
    docker_backup_tar = None
    for file in os.listdir(extract_dir):
        if file.startswith('docker_backup_') and file.endswith('.tar'):
            docker_backup_tar = os.path.join(extract_dir, file)
            break
    
    # Extract inner Docker backup if found
    if docker_backup_tar:
        print(f"Found inner Docker backup archive: {docker_backup_tar}")
        docker_extract_dir = os.path.join(extract_dir, "docker_data")
        os.makedirs(docker_extract_dir, exist_ok=True)
        
        with tarfile.open(docker_backup_tar, 'r:*') as tar:
            tar.extractall(path=docker_extract_dir)
        
        # Look for the actual docker backup directory inside
        for item in os.listdir(docker_extract_dir):
            item_path = os.path.join(docker_extract_dir, item)
            if os.path.isdir(item_path) and item.startswith('docker_backup_'):
                return item_path
        
        return docker_extract_dir
    
    return extract_dir


def restore_images(backup_dir):
    """
    Restore Docker images from backup
    
    Args:
        backup_dir (str): Path to the extracted backup directory
        
    Returns:
        list: List of restored image names
    """
    images_dir = os.path.join(backup_dir, 'images')
    
    if not os.path.exists(images_dir):
        print(f"No images found in {backup_dir}")
        return []
    
    restored_images = []
    
    for image_file in os.listdir(images_dir):
        if image_file.endswith('.tar'):
            image_path = os.path.join(images_dir, image_file)
            print(f"Loading image: {image_file}")
            result = run_command(f"docker load -i '{image_path}'")
            if result:
                # Extract image name from docker load output
                # Output format: "Loaded image: image:tag"
                if "Loaded image" in result:
                    image_name = result.split("Loaded image", 1)[1].strip(": \n")
                    restored_images.append(image_name)
                    print(f"Successfully loaded image: {image_name}")
                else:
                    print(f"Loaded image but couldn't determine name from: {result}")
    
    print(f"Restored {len(restored_images)} Docker images")
    return restored_images


def restore_volumes(backup_dir):
    """
    Restore Docker volumes from backup
    
    Args:
        backup_dir (str): Path to the extracted backup directory
        
    Returns:
        list: List of restored volume names
    """
    volumes_dir = os.path.join(backup_dir, 'volumes')
    
    if not os.path.exists(volumes_dir):
        print(f"No volumes found in {backup_dir}")
        return []
    
    restored_volumes = []
    
    # Get list of volume metadata files
    volume_files = [f for f in os.listdir(volumes_dir) if f.endswith('.json')]
    
    for volume_file in volume_files:
        volume_name = os.path.splitext(volume_file)[0]
        volume_path = os.path.join(volumes_dir, volume_file)
        
        # Check if volume already exists
        check_result = run_command(f"docker volume ls --format '{{{{.Name}}}}' --filter name=^{volume_name}$")
        if check_result and volume_name in check_result.splitlines():
            print(f"Volume {volume_name} already exists, skipping creation")
            restored_volumes.append(volume_name)
            continue
        
        # Create the volume
        print(f"Creating volume: {volume_name}")
        create_result = run_command(f"docker volume create {volume_name}")
        
        if create_result:
            # Restore volume data
            volume_data_dir = os.path.join(volumes_dir, volume_name)
            
            if os.path.exists(volume_data_dir) and os.path.isdir(volume_data_dir):
                # Use alpine to copy data from backup to the volume
                temp_container = f"volume_restore_{volume_name.replace('-', '_')}"
                print(f"Restoring data to volume: {volume_name}")
                restore_cmd = f"docker run --rm --name {temp_container} -v {volume_name}:/target -v {volume_data_dir}:/backup:ro alpine sh -c 'cd /backup && tar -cf - . | tar -xf - -C /target'"
                run_command(restore_cmd, capture_output=False)
                
                restored_volumes.append(volume_name)
                print(f"Successfully restored volume: {volume_name}")
            else:
                print(f"Volume {volume_name} created but no data to restore")
                restored_volumes.append(volume_name)
    
    print(f"Restored {len(restored_volumes)} Docker volumes")
    return restored_volumes


def restore_networks(backup_dir):
    """
    Restore Docker networks from backup
    
    Args:
        backup_dir (str): Path to the extracted backup directory
        
    Returns:
        list: List of restored network names
    """
    networks_dir = os.path.join(backup_dir, 'networks')
    
    if not os.path.exists(networks_dir):
        print(f"No networks found in {backup_dir}")
        return []
    
    restored_networks = []
    
    # Find all network JSON files
    for network_file in os.listdir(networks_dir):
        if network_file.endswith('.json'):
            network_path = os.path.join(networks_dir, network_file)
            network_name = os.path.splitext(network_file)[0]
            
            with open(network_path, 'r') as f:
                try:
                    # For networks, we often get an array with one object
                    network_config = json.load(f)
                    if isinstance(network_config, list):
                        network_config = network_config[0]
                
                    # Check if network already exists
                    check_result = run_command(f"docker network ls --format '{{{{.Name}}}}' --filter name=^{network_name}$")
                    if check_result and network_name in check_result.splitlines():
                        print(f"Network {network_name} already exists, skipping creation")
                        restored_networks.append(network_name)
                        continue
                    
                    # Skip default networks
                    if network_name in ['bridge', 'host', 'none']:
                        print(f"Skipping default network: {network_name}")
                        continue
                    
                    # Get network driver and options
                    driver = network_config.get('Driver', 'bridge')
                    
                    # Build network creation command
                    cmd = [f"docker network create --driver {driver}"]
                    
                    # Add any additional options (subnet, gateway, etc)
                    ipam_config = network_config.get('IPAM', {}).get('Config', [])
                    for config in ipam_config:
                        if 'Subnet' in config:
                            cmd.append(f"--subnet={config['Subnet']}")
                        if 'Gateway' in config:
                            cmd.append(f"--gateway={config['Gateway']}")
                            
                    # Add network name
                    cmd.append(network_name)
                    
                    # Create the network
                    print(f"Creating network: {network_name} with driver {driver}")
                    result = run_command(" ".join(cmd))
                    
                    if result:
                        restored_networks.append(network_name)
                        print(f"Successfully created network: {network_name}")
                except json.JSONDecodeError:
                    print(f"Error: Could not parse network configuration for {network_name}")
                except Exception as e:
                    print(f"Error creating network {network_name}: {e}")
    
    print(f"Restored {len(restored_networks)} Docker networks")
    return restored_networks


def restore_application_files(backup_file, target_dir):
    """
    Extract application files from backup to target directory
    
    Args:
        backup_file (str): Path to the backup file
        target_dir (str): Directory to extract to
    
    Returns:
        bool: True if files were extracted successfully
    """
    temp_dir = tempfile.mkdtemp(prefix="docker_extract_")
    success = False
    
    try:
        # Extract main archive
        with tarfile.open(backup_file, 'r:*') as tar:
            tar.extractall(path=temp_dir)
        
        # Find archives
        archive_files = find_backup_archives(temp_dir)
        
        # Extract current directory files
        if archive_files['current_dir']:
            success = extract_archive(archive_files['current_dir'], target_dir, "application files")
        else:
            print("No application files archive found in backup")
        
        # Extract docker source base directory
        if archive_files['docker_src_base_dir']:
            docker_src_dir = os.path.join(target_dir, "docker_src_base_dir")
            os.makedirs(docker_src_dir, exist_ok=True)
            success = extract_archive(archive_files['docker_src_base_dir'], docker_src_dir,  
                                    "Docker source base directory") or success
        
    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir)
    
    return success

def find_backup_archives(temp_dir):
    """Find different backup archives in the temp directory"""
    archives = {
        'current_dir': None,
        'docker_src_base_dir': None
    }
    
    for file in os.listdir(temp_dir):
        if file.startswith('current_dir_') and file.endswith('.tar'):
            archives['current_dir'] = os.path.join(temp_dir, file)
        elif file.startswith('additional_path_') and file.endswith('.tar'):
            # Legacy support for old archive name
            archives['docker_src_base_dir'] = os.path.join(temp_dir, file)
        elif file.startswith('docker_src_base_dir_') and file.endswith('.tar'):
            archives['docker_src_base_dir'] = os.path.join(temp_dir, file)
    
    return archives

def extract_archive(archive_path, target_dir, description):
    """Extract an archive file to target directory"""
    print(f"Found {description} archive: {os.path.basename(archive_path)}")
    print(f"Extracting {description} to: {target_dir}")
    
    with tarfile.open(archive_path, 'r:*') as tar:
        tar.extractall(path=target_dir)
    
    print(f"{description.capitalize()} successfully extracted")
    return True


def restore_containers(backup_dir, networks, volumes):
    """
    Restore Docker containers from backup
    
    Args:
        backup_dir (str): Path to the extracted backup directory
        networks (list): List of available networks
        volumes (list): List of available volumes
        
    Returns:
        list: List of restored container names
    """
    containers_file = os.path.join(backup_dir, 'containers.json')
    
    if not os.path.exists(containers_file):
        print(f"No containers found in {backup_dir}")
        return []
    
    with open(containers_file, 'r') as f:
        containers = json.load(f)
    
    restored_containers = []
    
    for container in containers:
        container_name = container.get('Name', '').strip('/')
        image = container.get('Config', {}).get('Image')
        
        if not container_name or not image:
            print(f"Missing container name or image for container: {container}")
            continue
        
        # Check if container already exists
        check_result = run_command(f"docker ps -a --format '{{{{.Names}}}}' --filter name=^{container_name}$")
        if check_result and container_name in check_result.splitlines():
            print(f"Container {container_name} already exists, skipping creation")
            restored_containers.append(container_name)
            continue
        
        # Build container creation command
        cmd = ["docker run -d"]
        
        # Add container name
        cmd.append(f"--name {container_name}")
        
        # Add restart policy
        restart_policy = container.get('HostConfig', {}).get('RestartPolicy', {}).get('Name')
        if restart_policy:
            cmd.append(f"--restart {restart_policy}")
        
        # Add port mappings
        port_bindings = container.get('HostConfig', {}).get('PortBindings', {})
        for container_port, host_bindings in port_bindings.items():
            for binding in host_bindings:
                host_port = binding.get('HostPort')
                if host_port:
                    cmd.append(f"-p {host_port}:{container_port.split('/')[0]}")
        
        # Add volume mounts
        mounts = container.get('HostConfig', {}).get('Mounts', [])
        for mount in mounts:
            source = mount.get('Source')
            target = mount.get('Target')
            if source and target and source in volumes:
                cmd.append(f"-v {source}:{target}")
        
        # Add environment variables
        env_vars = container.get('Config', {}).get('Env', [])
        for env in env_vars:
            if '=' in env:  # Only add properly formed env vars
                cmd.append(f"-e '{env}'")
        
        # Add networks
        container_networks = container.get('NetworkSettings', {}).get('Networks', {})
        for network_name in container_networks:
            if network_name in networks:
                cmd.append(f"--network {network_name}")
        
        # Add the image name
        cmd.append(image)
        
        # Add command if present
        container_cmd = container.get('Config', {}).get('Cmd')
        if container_cmd and isinstance(container_cmd, list):
            cmd.append(" ".join(container_cmd))
        
        # Create the container
        print(f"Creating container: {container_name}")
        full_cmd = " ".join(cmd)
        print(f"Command: {full_cmd}")
        result = run_command(full_cmd)
        
        if result:
            restored_containers.append(container_name)
            print(f"Successfully created container: {container_name}")
    
    print(f"Restored {len(restored_containers)} Docker containers")
    return restored_containers


def restore_docker_backup(backup_file, extract_dir=None, compose_file_path=None):
    """
    Restore a Docker backup with proper Docker Compose integration
    """
    print(f"Starting Docker restoration from {backup_file}")
    
    # Extract the backup
    backup_dir = extract_backup(backup_file, extract_dir)
    
    # Extract application files 
    current_dir = os.getcwd()
    app_files_extracted = restore_application_files(backup_file, current_dir)
    
    # Restore images - they don't have Compose-specific labels
    restored_images = restore_images(backup_dir)
    
    # Find the compose file to use
    compose_file = find_compose_file(compose_file_path, current_dir)
    
    # Restore using compose or direct method
    if compose_file:
        restored_networks, restored_containers = restore_with_compose(compose_file, backup_dir)
    else:
        print("\nWarning: No docker-compose.yml found after extraction.")
        print("Falling back to direct restoration, but Docker Compose commands won't work properly.")
        
        # Fall back to direct network/container restoration without labels
        restored_networks = restore_networks(backup_dir)
        restored_volumes = restore_volumes(backup_dir)
        restored_containers = restore_containers(backup_dir, restored_networks, restored_volumes)
    
    print(f"\nDocker restoration complete!")
    print(f"Restored {len(restored_images)} images, {len(restored_networks)} networks, and {len(restored_containers)} containers")
    
    return (restored_images, restored_networks, restored_containers)


def find_compose_file(compose_file_path, current_dir):
    """Find the docker-compose file to use for restoration"""
    # Use provided compose file path if available
    if compose_file_path and os.path.exists(compose_file_path):
        print(f"Using specified docker-compose.yml at: {compose_file_path}")
        return compose_file_path
    elif compose_file_path:
        print(f"Warning: Specified docker-compose.yml not found at {compose_file_path}")
    
    # Check default locations
    default_compose_file = os.path.join(current_dir, 'docker-compose.yml')
    default_compose_yaml_file = os.path.join(current_dir, 'docker-compose.yaml')
    
    if os.path.exists(default_compose_file):
        print(f"Found docker-compose.yml in current directory")
        return default_compose_file
    elif os.path.exists(default_compose_yaml_file):
        print(f"Found docker-compose.yaml in current directory")
        return default_compose_yaml_file
    
    return None


def restore_with_compose(compose_file, backup_dir):
    """Restore Docker resources using docker-compose"""
    print(f"Found docker-compose file: {compose_file}")
    
    try:
        # Use Docker Compose to create networks and containers with proper labels
        compose_cmd = f"docker compose -f {compose_file} up -d"
        run_command(compose_cmd, capture_output=False)
        
        # Get the list of containers created by Docker Compose
        containers_str = run_command(f"docker compose -f {compose_file} ps -q")
        restored_containers = containers_str.split() if containers_str else []
        
        # Get the list of networks created by Docker Compose
        networks_str = run_command("docker network ls --filter 'label=com.docker.compose.project' --format '{{.Name}}'")
        restored_networks = networks_str.split() if networks_str else []
        
        return restored_networks, restored_containers
    except Exception as e:
        print(f"Error using Docker Compose: {e}")
        print("Falling back to direct restoration method")
        
        # Fall back to direct restoration
        restored_networks = restore_networks(backup_dir)
        restored_volumes = restore_volumes(backup_dir)
        restored_containers = restore_containers(backup_dir, restored_networks, restored_volumes)
        
        return restored_networks, restored_containers


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Docker Backup and Restoration Tool')
    parser.add_argument('--action', choices=['backup', 'restore'], default='backup',
                      help='Action to perform: backup or restore')
    parser.add_argument('--backup-file', help='Path to backup file (for restore)')
    parser.add_argument('--extract-dir', help='Directory to extract backup (for restore)')
    parser.add_argument('--backup-dir', default='./__docker_backup',
                      help='Directory to store backup (for backup)')
    parser.add_argument('--include-current-dir', action='store_true',
                      help='Include current directory in backup (for backup)')
    parser.add_argument('--destination', default='~/docker_backups',
                      help='Destination path for backup transfer (for backup)')
    
    args = parser.parse_args()
    
    if args.action == 'backup':
        backup_dir = args.backup_dir
        backup_file = create_docker_backup(backup_dir, include_current_dir=args.include_current_dir)
        transfer_backup(backup_file, args.destination)
    elif args.action == 'restore':
        if not args.backup_file:
            print("Error: --backup-file is required for restore action")
            parser.print_help()
            return
        restore_docker_backup(args.backup_file, args.extract_dir)


if __name__ == "__main__":
    main()