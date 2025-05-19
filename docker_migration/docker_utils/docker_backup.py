import os
import json
import tempfile
import tarfile
import shutil
import subprocess
import datetime
import time  # Important for the container naming
import yaml
import glob
import docker  # Add this import


def run_command(cmd, capture_output=True, use_sudo=False):
    """Run a shell command and return the output"""
    try:
        # Add sudo if required for any command when use_sudo is True
        if use_sudo:
            # Don't add sudo if it's already there
            if not cmd.strip().startswith("sudo "):
                cmd = f"sudo {cmd}"
        
        print(f"Executing: {cmd}")
        result = subprocess.run(cmd, shell=True, check=True, 
                              text=True, capture_output=capture_output)
        return result.stdout.strip() if capture_output else True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}")
        print(f"Return code: {e.returncode}")
        if capture_output and hasattr(e, 'stderr'):
            print(f"Error output: {e.stderr}")
        # Return empty string for silent failure handling
        return "" if capture_output else False


def backup_docker_data(images=True, containers=True, networks=True, volumes=True, compose_file=None, config_only=False, backup_all=False, pull_images=False, no_prompt=False, include_current_dir=None):
    """Backup Docker data including images, containers, and configurations"""
    # Create a timestamped backup directory if one wasn't provided
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"docker_backup_{timestamp}"
    
    os.makedirs(backup_dir, exist_ok=True)
    print(f"Backing up Docker data to: {backup_dir}")
    
    extracted_data = {}
    
    # Back up images
    if images:
        all_images_raw = run_command("docker images --format '{{.Repository}}:{{.Tag}}'")
        available_images = [img for img in all_images_raw.splitlines() if img != "<none>:<none>"]
        
        if backup_all:
            images_to_backup = available_images
        else:
            # Extract image names from compose file if provided
            if compose_file and os.path.exists(compose_file):
                with open(compose_file, 'r') as f:
                    compose_data = yaml.safe_load(f)
                    services = compose_data.get('services', {})
                    images_to_backup = [svc.get('image') for svc in services.values() if svc.get('image')]
            else:
                images_to_backup = []
        
        if images_to_backup:
            print(f"Backing up {len(images_to_backup)} images: {', '.join(images_to_backup)}")
            backed_up_images = backup_images(backup_dir, images_to_backup)
            extracted_data['images'] = backed_up_images
        else:
            print("No images specified to back up")
    
    # Back up containers
    if containers:
        all_containers_raw = run_command("docker ps -a --format '{{.Names}}'")
        all_containers = all_containers_raw.splitlines() if all_containers_raw else []
        
        if backup_all:
            containers_to_backup = all_containers
        else:
            # Extract container names from compose file if provided
            if compose_file and os.path.exists(compose_file):
                with open(compose_file, 'r') as f:
                    compose_data = yaml.safe_load(f)
                    services = compose_data.get('services', {})
                    containers_to_backup = [svc.get('container_name') for svc in services.values() if svc.get('container_name')]
            else:
                containers_to_backup = []
        
        if containers_to_backup:
            print(f"Backing up {len(containers_to_backup)} containers: {', '.join(containers_to_backup)}")
            backed_up_containers = backup_containers(backup_dir, containers_to_backup)
            extracted_data['containers'] = backed_up_containers
        else:
            print("No containers specified to back up")
    
    # Back up networks
    if networks:
        print("\n=== Starting Docker network backup ===")
        if backup_all:
            all_networks = run_command("docker network ls --format '{{.Name}}'").splitlines()
            networks_to_backup = all_networks
        else:
            # Extract network names from compose file if provided
            if compose_file and os.path.exists(compose_file):
                with open(compose_file, 'r') as f:
                    compose_data = yaml.safe_load(f)
                    
                    # Get named networks from 'networks' section
                    if 'networks' in compose_data:
                        networks_to_backup.extend(compose_data['networks'].keys())
                    
                    # Get networks used in services
                    services = compose_data.get('services', {})
                    for service in services.values():
                        if 'networks' in service:
                            service_networks = service['networks']
                            if isinstance(service_networks, list):
                                networks_to_backup.extend(service_networks)
                            elif isinstance(service_networks, dict):
                                networks_to_backup.extend(service_networks.keys())
        
        # Remove duplicates while preserving order
        networks_to_backup = list(dict.fromkeys(networks_to_backup))
        
        if networks_to_backup:
            print(f"Backing up {len(networks_to_backup)} networks: {', '.join(networks_to_backup)}")
            backed_up_networks = backup_networks(backup_dir, networks_to_backup)
            extracted_data['networks'] = backed_up_networks
        else:
            print("No networks specified to back up")
    
    # ADD THIS SECTION: Back up volumes with proper logging
    if volumes:
        print("\n=== Starting Docker volume backup ===")
        if backup_all:
            volumes_to_backup = run_command("docker volume ls -q").splitlines()
        else:
            # Extract volume names from compose file if provided
            volumes_to_backup = []
            if compose_file and os.path.exists(compose_file):
                try:
                    with open(compose_file, 'r') as f:
                        compose_data = yaml.safe_load(f)
                        
                        # Get named volumes from 'volumes' section
                        if 'volumes' in compose_data:
                            print(f"Found {len(compose_data['volumes'])} named volumes in docker-compose.yml")
                            volumes_to_backup.extend(compose_data['volumes'].keys())
                        
                        # Get volumes used in services
                        services = compose_data.get('services', {})
                        for service_name, service in services.items():
                            if 'volumes' in service:
                                print(f"Found volumes in service '{service_name}'")
                                for vol in service['volumes']:
                                    # Handle different volume syntaxes
                                    if isinstance(vol, str) and ':' in vol:
                                        vol_parts = vol.split(':', 1)
                                        # Only add named volumes (not bind mounts)
                                        if not vol_parts[0].startswith('./') and not vol_parts[0].startswith('/'):
                                            volumes_to_backup.append(vol_parts[0])
                                            print(f"  - Added volume: {vol_parts[0]}")
                except Exception as e:
                    print(f"Error extracting volumes from compose file: {e}")
        
        # Remove duplicates while preserving order
        volumes_to_backup = list(dict.fromkeys(volumes_to_backup))
        
        if volumes_to_backup:
            print(f"Backing up {len(volumes_to_backup)} volumes: {', '.join(volumes_to_backup)}")
            backed_up_volumes = backup_volumes(backup_dir, volumes_to_backup)
            extracted_data['volumes'] = backed_up_volumes
        else:
            print("No volumes specified to back up")
    
    # Optionally pull latest images
    if pull_images and images:
        for image in images_to_backup:
            print(f"Pulling latest image: {image}")
            run_command(f"docker pull {image}")
    
    print("Docker data backup completed")
    
    # After all Docker resources are backed up
    
    # Check if we should include the current directory
    if include_current_dir is not None:
        # Use the value passed from main.py
        pass
    elif no_prompt:
        include_current_dir = True
    else:
        # Only prompt if a value wasn't provided and no_prompt is False
        while include_current_dir is None:
            response = input("Do you want to include the current directory in the backup? (yes/no): ").strip().lower()
            if response in ['yes', 'y']:
                include_current_dir = True
            elif response in ['no', 'n']:
                include_current_dir = False
            else:
                print("Please enter 'yes' or 'no'")
    
    if include_current_dir:
        # Code to include current directory in backup...
        current_dir = os.getcwd()
        print(f"Including current directory: {current_dir}")
        
        # Create additional_files archive
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        additional_files_archive = os.path.join(backup_dir, f"additional_files_{timestamp}.tar")
        
        # Create the tar archive
        with tarfile.open(additional_files_archive, "w") as tar:
            tar.add(".", arcname="./")
        
        print(f"Current directory backed up to {additional_files_archive}")
    
    return backup_dir


def backup_all_docker_data(skip_images=False, skip_containers=False):
    """
    Backup all Docker data using CLI commands
    
    Args:
        skip_images (bool): Skip backing up images
        skip_containers (bool): Skip backing up containers
    
    Returns:
        tuple: (backup_dir, images, containers, networks)
    """
    images = []
    containers = []
    networks = []
    volumes = []
    
    # Get all running containers
    if not skip_containers:
        all_containers_raw = run_command("docker ps -a --format '{{.Names}}'")
        containers = all_containers_raw.splitlines() if all_containers_raw else []
    
    # Get all images
    if not skip_images:
        all_images_raw = run_command("docker images --format '{{.Repository}}:{{.Tag}}'")
        images = [img for img in all_images_raw.splitlines() if img != "<none>:<none>"] if all_images_raw else []
    
    # Get all networks (always include)
    all_networks_raw = run_command("docker network ls --format '{{.Name}}' --filter 'type=custom'")
    networks = all_networks_raw.splitlines() if all_networks_raw else []
    
    # Get all volumes (always include)
    all_volumes_raw = run_command("docker volume ls --format '{{.Name}}'")
    volumes = all_volumes_raw.splitlines() if all_volumes_raw else []
    
    # Backup data
    backup_dir = backup_docker_data(
        images if not skip_images else [], 
        containers if not skip_containers else [], 
        networks, 
        volumes
    )
    
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


def backup_containers(backup_dir, containers_to_backup=None):
    """Backup Docker containers"""
    containers_dir = os.path.join(backup_dir, 'containers')
    os.makedirs(containers_dir, exist_ok=True)
    
    # Get list of all containers
    all_containers_raw = run_command("docker ps -a --format '{{.Names}}'")
    all_containers = all_containers_raw.splitlines() if all_containers_raw else []
    
    print(f"Found {len(all_containers)} Docker containers on the system (including stopped)")
    print(f"Available containers: {', '.join(all_containers)}")
    
    # If no specific containers are specified, back up all
    if not containers_to_backup:
        containers_to_backup = all_containers
        print(f"Backing up all {len(all_containers)} containers")
    
    backed_up_containers = []
    for container in containers_to_backup:
        print(f"Looking for container: {container}")
        
        # Check if container exists
        if container in all_containers:
            print(f"Found container: {container}")
            
            # Export container configuration
            container_config_file = os.path.join(containers_dir, f"{container}.json")
            try:
                container_config = run_command(f"docker inspect {container}")
                if container_config:
                    with open(container_config_file, 'w') as f:
                        f.write(container_config)
                    
                    # Make a commit of the container to save its state
                    container_image = f"{container}_backup_image"
                    run_command(f"docker commit {container} {container_image}")
                    
                    # Save the committed image
                    image_file = os.path.join(containers_dir, f"{container}.tar")
                    run_command(f"docker save -o {image_file} {container_image}")
                    
                    # Remove the temporary image
                    run_command(f"docker rmi {container_image}")
                    
                    backed_up_containers.append(container)
                    print(f"Successfully backed up container: {container}")
            except Exception as e:
                print(f"Error backing up container {container}: {e}")
        else:
            print(f"Container {container} not found with any naming pattern")
    
    print(f"Successfully backed up {len(backed_up_containers)} of {len(containers_to_backup)} containers")
    return backed_up_containers


def backup_volumes(backup_dir, volumes_to_backup=None):
    """Backup Docker volumes"""
    volumes_dir = os.path.join(backup_dir, 'volumes')
    os.makedirs(volumes_dir, exist_ok=True)
    
    print("\n=== Starting Docker volume backup ===")
    
    # Get list of all volumes
    all_volumes_raw = run_command("docker volume ls -q")
    available_volumes = all_volumes_raw.splitlines() if all_volumes_raw else []
    
    print(f"Found {len(available_volumes)} Docker volumes on the system")
    
    # If no specific volumes are specified, back up all
    if not volumes_to_backup:
        volumes_to_backup = available_volumes
        print(f"Backing up all {len(available_volumes)} volumes")
    else:
        print(f"Backing up {len(volumes_to_backup)} specified volumes: {', '.join(volumes_to_backup)}")
    
    backed_up_volumes = []
    for volume in volumes_to_backup:
        print(f"Processing volume: {volume}")
        
        # Skip if volume doesn't exist
        if volume not in available_volumes:
            print(f"Volume {volume} not found - skipping")
            continue
            
        try:
            # Create a temporary container to access the volume
            timestamp = int(time.time())
            container_name = f"volume_backup_{volume.replace('-', '_')}_{timestamp}"
            
            run_command(f"docker run -d --name {container_name} -v {volume}:/volume alpine:latest sleep 60")
            
            # Create archive of the volume data
            volume_archive = os.path.join(volumes_dir, f"{volume.replace('/', '_')}.tar")
            print(f"Creating archive for volume {volume}...")
            
            # Create tar archive inside the container
            run_command(f"docker exec {container_name} tar -cf /tmp/volume.tar -C /volume .")
            
            # Copy the archive from the container
            run_command(f"docker cp {container_name}:/tmp/volume.tar {volume_archive}")
            
            # Clean up the temporary container
            run_command(f"docker rm -f {container_name}")
            
            backed_up_volumes.append(volume)
            print(f"Successfully backed up volume: {volume}")
        except Exception as e:
            print(f"Error backing up volume {volume}: {e}")
    
    print(f"=== Volume backup complete: {len(backed_up_volumes)} of {len(volumes_to_backup)} volumes backed up ===\n")
    return backed_up_volumes


def backup_images(backup_dir, images_to_backup=None):
    """Backup Docker images"""
    images_dir = os.path.join(backup_dir, 'images')
    os.makedirs(images_dir, exist_ok=True)
    
    # Get list of all images
    all_images_raw = run_command("docker images --format '{{.Repository}}:{{.Tag}}'")
    available_images = [img for img in all_images_raw.splitlines() if img != "<none>:<none>"]
    
    # If no specific images are specified, back up all
    if not images_to_backup:
        images_to_backup = available_images
        print(f"Backing up all {len(available_images)} images")
    
    print(f"Attempting to back up {len(images_to_backup)} images from compose file")
    backed_up_images = []
    
    for image in images_to_backup:
        print(f"Looking for image: {image}")
        
        # Check if image exists
        if image in available_images:
            print(f"Found exact match: {image}")
            
            # Save the image
            image_file = os.path.join(images_dir, f"{image.replace(':', '_').replace('/', '_')}.tar")
            try:
                run_command(f"docker save -o {image_file} {image}")
                backed_up_images.append(image)
                print(f"Successfully backed up image: {image}")
            except Exception as e:
                print(f"Error backing up image {image}: {e}")
        else:
            # Try to find a similar image
            print(f"Warning: Image {image} not found on the system")
            print(f"  Possible matches: {', '.join(available_images[:5])}")
            if available_images:
                print(f"  Trying first match: {available_images[0]}")
                
                # Save the first available image as a fallback
                image_file = os.path.join(images_dir, f"{available_images[0].replace(':', '_').replace('/', '_')}.tar")
                try:
                    run_command(f"docker save -o {image_file} {available_images[0]}")
                    backed_up_images.append(available_images[0])
                    print(f"  Successfully backed up {available_images[0]} as a fallback")
                except Exception as e:
                    print(f"  Error backing up fallback image {available_images[0]}: {e}")
    
    print(f"Successfully backed up {len(backed_up_images)} of {len(images_to_backup)} images")
    return backed_up_images


def backup_networks(backup_dir, networks_to_backup=None):
    """Backup Docker networks"""
    networks_dir = os.path.join(backup_dir, 'networks')
    os.makedirs(networks_dir, exist_ok=True)
    
    # Get list of all networks
    all_networks_raw = run_command("docker network ls --format '{{.Name}}'")
    available_networks = all_networks_raw.splitlines() if all_networks_raw else []
    
    print(f"\nFound {len(available_networks)} Docker networks on the system")
    
    # If no specific networks are specified, back up all
    if not networks_to_backup:
        networks_to_backup = available_networks
        print(f"Backing up all {len(available_networks)} networks")
    else:
        print(f"Backing up {len(networks_to_backup)} specified networks: {', '.join(networks_to_backup)}")
    
    backed_up_networks = []
    for network in networks_to_backup:
        print(f"Looking for network: {network}")
        
        # Check if network exists
        if network in available_networks:
            print(f"Found network: {network}")
            
            # Export network configuration
            network_config_file = os.path.join(networks_dir, f"{network}.json")
            try:
                network_config = run_command(f"docker network inspect {network}")
                if network_config:
                    with open(network_config_file, 'w') as f:
                        f.write(network_config)
                    
                    backed_up_networks.append(network)
                    print(f"Successfully backed up network: {network}")
            except Exception as e:
                print(f"Error backing up network {network}: {e}")
        else:
            print(f"Network {network} not found")
    
    print(f"Successfully backed up {len(backed_up_networks)} of {len(networks_to_backup)} networks\n")
    return backed_up_networks


def ensure_image_available(image_name):
    """Make sure an image is available, pulling it if needed"""
    check_cmd = f"docker image ls -q {image_name}"
    if not run_command(check_cmd):
        print(f"Image {image_name} not found, pulling...")
        pull_cmd = f"docker pull {image_name}"
        return run_command(pull_cmd, capture_output=False)
    return True