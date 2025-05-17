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


def backup_docker_data(images, containers, networks):
    """
    Backup specified Docker data using Docker CLI
    
    Args:
        images (list): List of image names to backup
        containers (list): List of container IDs to backup
        networks (list): List of network IDs to backup
        
    Returns:
        str: Path to the Docker backup directory
    """
    # Create a backup directory
    backup_dir = tempfile.mkdtemp(prefix="docker_backup_")
    print(f"Creating Docker backup in {backup_dir}")
    
    # Save container details and identify volumes
    containers_json = []
    existing_containers = []
    volumes_to_backup = set()  # Use a set to avoid duplicates
    
    # First check which containers actually exist and identify volumes
    for container_id in containers:
        container_info = run_command(f"docker inspect {container_id}")
        if container_info:
            try:
                container_data = json.loads(container_info)[0]
                containers_json.append(container_data)
                existing_containers.append(container_id)
                
                # Extract volume information
                mounts = container_data.get('Mounts', [])
                for mount in mounts:
                    if mount.get('Type') == 'volume':
                        volumes_to_backup.add(mount.get('Name'))
                        
            except json.JSONDecodeError:
                print(f"Warning: Could not parse JSON for container {container_id}")
        else:
            print(f"Warning: Container {container_id} not found, it will be skipped")
    
    # Update the containers list to only include existing containers
    containers = existing_containers
    
    with open(os.path.join(backup_dir, 'containers.json'), 'w') as f:
        json.dump(containers_json, f, indent=2)
    
    # Save images
    os.makedirs(os.path.join(backup_dir, 'images'), exist_ok=True)
    for image_name in images:
        print(f"Saving image: {image_name}")
        image_filename = os.path.join(backup_dir, 'images', image_name.replace('/', '_').replace(':', '_') + '.tar')
        run_command(f"docker save -o '{image_filename}' '{image_name}'", capture_output=False)
        run_command(f"chmod 644 '{image_filename}'", capture_output=False)
    
    # Save networks
    existing_networks = []
    networks_json = []
    
    os.makedirs(os.path.join(backup_dir, 'networks'), exist_ok=True)
    for network_name in networks:
        network_info = run_command(f"docker network inspect {network_name}")
        if network_info:
            try:
                network_data = json.loads(network_info)
                networks_json.extend(network_data)
                existing_networks.append(network_name)
                
                # Save the network configuration
                network_filename = os.path.join(backup_dir, 'networks', network_name + '.json')
                with open(network_filename, 'w') as f:
                    f.write(network_info)
                    
                print(f"Saved network configuration for: {network_name}")
            except json.JSONDecodeError:
                print(f"Warning: Could not parse JSON for network {network_name}")
        else:
            print(f"Warning: Network {network_name} not found, it will be skipped")
    
    # Save volumes
    os.makedirs(os.path.join(backup_dir, 'volumes'), exist_ok=True)
    for volume_name in volumes_to_backup:
        print(f"Backing up volume: {volume_name}")
        
        # Get volume info
        volume_info = run_command(f"docker volume inspect {volume_name}")
        if volume_info:
            try:
                # Save volume metadata
                volume_data = json.loads(volume_info)
                volume_meta_file = os.path.join(backup_dir, 'volumes', f"{volume_name}.json")
                with open(volume_meta_file, 'w') as f:
                    f.write(volume_info)
                
                # Export volume data using a temporary container
                volume_dir = os.path.join(backup_dir, 'volumes', volume_name)
                os.makedirs(volume_dir, exist_ok=True)
                
                # Use alpine to copy data from volume to our backup directory
                temp_container = f"volume_backup_{volume_name.replace('-', '_')}"
                run_command(f"docker run --rm --name {temp_container} -v {volume_name}:/source -v {volume_dir}:/backup:rw alpine sh -c 'cd /source && tar -cf - . | tar -xf - -C /backup'", capture_output=False)
                
                print(f"Volume {volume_name} data backed up successfully")
            except json.JSONDecodeError:
                print(f"Warning: Could not parse JSON for volume {volume_name}")
        else:
            print(f"Warning: Volume {volume_name} not found, it will be skipped")

    # Create a manifest file with metadata including volumes
    with open(os.path.join(backup_dir, 'manifest.json'), 'w') as f:
        json.dump({
            'images': images,
            'containers': containers,
            'networks': existing_networks,
            'volumes': list(volumes_to_backup),
            'date': str(datetime.datetime.now()),
            'docker_version': run_command("docker version --format '{{.Server.Version}}'")
        }, f, indent=2)
    
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
    # Get all containers
    containers_raw = run_command("docker ps -a --format '{{.ID}}'")
    containers = containers_raw.splitlines() if containers_raw else []
    
    # Get all images used by those containers
    images = []
    for container in containers:
        image = run_command(f"docker inspect --format='{{{{.Config.Image}}}}' {container}")
        if image:
            images.append(image)
    
    # Get all networks used
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
    """Extract application files from backup to target directory"""
    temp_dir = tempfile.mkdtemp(prefix="docker_extract_")
    
    try:
        # Extract main archive
        with tarfile.open(backup_file, 'r:*') as tar:
            tar.extractall(path=temp_dir)
        
        # Find and extract current_dir archive
        current_dir_tar = None
        for file in os.listdir(temp_dir):
            if file.startswith('current_dir_') and file.endswith('.tar'):
                current_dir_tar = os.path.join(temp_dir, file)
                break
        
        if current_dir_tar:
            print(f"Found application files archive: {current_dir_tar}")
            print(f"Extracting application files to: {target_dir}")
            with tarfile.open(current_dir_tar, 'r:*') as tar:
                tar.extractall(path=target_dir)
            print("Application files successfully extracted")
        else:
            print("No application files archive found in backup")
    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir)


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


def restore_docker_backup(backup_file, extract_dir=None):
    """
    Restore a Docker backup with proper Docker Compose integration
    
    Args:
        backup_file (str): Path to the backup file
        extract_dir (str, optional): Directory to extract to
        
    Returns:
        tuple: (restored_images, restored_networks, restored_containers)
    """
    print(f"Starting Docker restoration from {backup_file}")
    
    # Extract the backup
    backup_dir = extract_backup(backup_file, extract_dir)
    
    # First, extract application files (docker-compose.yml and related files)
    current_dir = os.getcwd()
    app_files_extracted = extract_application_files(backup_file, current_dir)
    
    # Restore images only - they don't have Compose-specific labels
    restored_images = restore_images(backup_dir)
    
    # Check if docker-compose.yml exists in current directory
    compose_file = os.path.join(current_dir, 'docker-compose.yml')
    compose_yaml_file = os.path.join(current_dir, 'docker-compose.yaml')
    
    if os.path.exists(compose_file) or os.path.exists(compose_yaml_file):
        # Extract volume data to a temporary location
        volumes_dir = os.path.join(backup_dir, 'volumes')
        temp_volumes_data = None
        
        if os.path.exists(volumes_dir):
            # Save volume data for later restoration
            temp_volumes_data = os.path.join(tempfile.mkdtemp(), 'volume_data')
            shutil.copytree(volumes_dir, temp_volumes_data)
        
        # Check for existing resources that might conflict with Docker Compose
        print("Checking for existing Docker resources that might conflict with Docker Compose...")
        
        # Get networks from docker-compose.yml to check for conflicts
        networks_to_check = []
        try:
            import yaml # type: ignore
            if os.path.exists(compose_file):
                with open(compose_file, 'r') as f:
                    compose_data = yaml.safe_load(f)
            else:
                with open(compose_yaml_file, 'r') as f:
                    compose_data = yaml.safe_load(f)
            
            # Extract network names
            if compose_data and 'networks' in compose_data:
                networks_to_check = list(compose_data['networks'].keys())
                
                # For each network, check if it exists and add external: true if needed
                for network in networks_to_check:
                    # Check if network exists
                    check_result = run_command(f"docker network ls --format '{{{{.Name}}}}' --filter name={network}")
                    if check_result and network in check_result.splitlines():
                        print(f"Network {network} already exists, marking as external in docker-compose.yml")
                        # Add external: true to the network in docker-compose.yml
                        compose_data['networks'][network]['external'] = True
                
                # Write the updated docker-compose.yml
                if os.path.exists(compose_file):
                    with open(compose_file, 'w') as f:
                        yaml.dump(compose_data, f)
                else:
                    with open(compose_yaml_file, 'w') as f:
                        yaml.dump(compose_data, f)
                
        except Exception as e:
            print(f"Warning: Error parsing docker-compose.yml: {e}")
        
        print("\nStarting containers using Docker Compose...")
        # Use Docker Compose to create networks and containers with proper labels
        result = run_command("docker compose up -d", capture_output=False)
        
        if result:
            print("Docker Compose successfully started containers with proper labels")
            # Get the list of containers created by Docker Compose
            containers_str = run_command("docker compose ps -q")
            restored_containers = containers_str.split() if containers_str else []
            
            # Get the list of networks created by Docker Compose
            networks_str = run_command("docker network ls --filter 'label=com.docker.compose.project' --format '{{.Name}}'")
            restored_networks = networks_str.split() if networks_str else []
            
            # Restore volume data if available
            if temp_volumes_data:
                print("\nRestoring volume data...")
                for volume_dir in os.listdir(temp_volumes_data):
                    if os.path.isdir(os.path.join(temp_volumes_data, volume_dir)):
                        volume_data_path = os.path.join(temp_volumes_data, volume_dir)
                        # Use docker run to copy data into the volume
                        print(f"Restoring data for volume: {volume_dir}")
                        
                        # Create a temporary container to copy data
                        temp_container = f"vol_restore_{volume_dir}"
                        run_command(f"docker run --rm -d --name {temp_container} -v {volume_dir}:/target alpine sleep 60")
                        
                        # Copy data into the volume
                        run_command(f"docker cp {volume_data_path}/. {temp_container}:/target/", capture_output=False)
                        
                        # Stop and remove the temp container
                        run_command(f"docker stop {temp_container}")
                
                # Clean up temporary directory
                shutil.rmtree(os.path.dirname(temp_volumes_data))
        else:
            print("Warning: Docker Compose failed to start containers. Falling back to direct restoration.")
            # Fall back to direct network/container restoration without labels
            restored_networks = restore_networks(backup_dir)
            restored_containers = restore_containers(backup_dir, restored_networks, [])
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


def extract_application_files(backup_file, target_dir):
    """Extract application files from backup to target directory
    
    Returns:
        bool: True if files were extracted successfully
    """
    temp_dir = tempfile.mkdtemp(prefix="docker_extract_")
    success = False
    
    try:
        # Extract main archive
        with tarfile.open(backup_file, 'r:*') as tar:
            tar.extractall(path=temp_dir)
        
        # Find and extract current_dir archive
        current_dir_tar = None
        for file in os.listdir(temp_dir):
            if file.startswith('current_dir_') and file.endswith('.tar'):
                current_dir_tar = os.path.join(temp_dir, file)
                break
        
        if current_dir_tar:
            print(f"Found application files archive: {current_dir_tar}")
            print(f"Extracting application files to: {target_dir}")
            with tarfile.open(current_dir_tar, 'r:*') as tar:
                tar.extractall(path=target_dir)
            print("Application files successfully extracted")
            success = True
        else:
            print("No application files archive found in backup")
            success = False
    finally:
        # Clean up temp directory
        shutil.rmtree(temp_dir)
    
    return success


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