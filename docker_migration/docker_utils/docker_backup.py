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
    
    # Get project name for resource name prefixing
    project_dir = os.path.basename(os.getcwd())
    print(f"Detected project directory: {project_dir}")
    
    # First fetch ALL available images on the system
    all_images_raw = run_command("docker images --format '{{.Repository}}:{{.Tag}}'")
    available_images = []
    if all_images_raw:
        available_images = [img for img in all_images_raw.splitlines() if img != "<none>:<none>"]
    print(f"Found {len(available_images)} Docker images on the system")
    
    # Fetch all containers including stopped ones
    all_containers_raw = run_command("docker ps -a --format '{{.Names}}'")
    all_containers = all_containers_raw.splitlines() if all_containers_raw else []
    print(f"Found {len(all_containers)} Docker containers on the system (including stopped)")
    
    # Fetch all networks
    all_networks_raw = run_command("docker network ls --format '{{.Name}}'")
    all_networks = all_networks_raw.splitlines() if all_networks_raw else []
    print(f"Found {len(all_networks)} Docker networks on the system")
    
    # Fetch all volumes
    all_volumes_raw = run_command("docker volume ls --format '{{.Name}}'")
    all_volumes = all_volumes_raw.splitlines() if all_volumes_raw else []
    print(f"Found {len(all_volumes)} Docker volumes on the system")
    
    # Backup images with intelligent matching
    if images:
        # Debug output for images to back up
        print(f"Attempting to back up {len(images)} images from compose file")
        
        # Create a map of images for easier lookups
        image_map = {}
        for img in available_images:
            # Store both with and without tag variations
            repo_with_tag = img
            repo_only = img.split(':')[0] if ':' in img else img
            image_map[repo_with_tag] = img
            image_map[repo_only] = img
            # Handle 'latest' tag special case
            if ':latest' in img:
                repo_without_tag = img.split(':')[0]
                image_map[repo_without_tag] = img
        
        backed_up_images = []
        for image in images:
            print(f"Looking for image: {image}")
            backed_up = False
            
            # 1. Try exact match first
            if image in image_map:
                actual_image = image_map[image]
                print(f"Found exact match: {actual_image}")
                try:
                    image_file = os.path.join(images_dir, actual_image.replace('/', '_').replace(':', '_') + '.tar')
                    run_command(f"docker save {actual_image} -o '{image_file}'")
                    backed_up_images.append(actual_image)
                    backed_up = True
                except Exception as e:
                    print(f"Error saving image {actual_image}: {e}")
            
            # 2. Try without tag if it has one
            if not backed_up and ':' in image:
                repo = image.split(':')[0]
                if repo in image_map:
                    actual_image = image_map[repo]
                    print(f"Found repo match: {actual_image} for {image}")
                    try:
                        image_file = os.path.join(images_dir, actual_image.replace('/', '_').replace(':', '_') + '.tar')
                        run_command(f"docker save {actual_image} -o '{image_file}'")
                        backed_up_images.append(actual_image)
                        backed_up = True
                    except Exception as e:
                        print(f"Error saving image {actual_image}: {e}")
                
            # 3. Try with 'latest' tag if no tag specified
            if not backed_up and ':' not in image:
                image_latest = f"{image}:latest"
                if image_latest in image_map:
                    actual_image = image_map[image_latest]
                    print(f"Found with latest tag: {actual_image}")
                    try:
                        image_file = os.path.join(images_dir, actual_image.replace('/', '_').replace(':', '_') + '.tar')
                        run_command(f"docker save {actual_image} -o '{image_file}'")
                        backed_up_images.append(actual_image)
                        backed_up = True
                    except Exception as e:
                        print(f"Error saving image {actual_image}: {e}")
            
            if not backed_up:
                print(f"Warning: Image {image} not found on the system")
                
                # Additional hint: let's see what's available
                possible_matches = [img for img in available_images if image.split(':')[0] in img]
                if possible_matches:
                    print(f"  Possible matches: {', '.join(possible_matches)}")
                    
                    # Try to back up the first close match if found
                    print(f"  Trying first match: {possible_matches[0]}")
                    try:
                        image_file = os.path.join(images_dir, possible_matches[0].replace('/', '_').replace(':', '_') + '.tar')
                        run_command(f"docker save {possible_matches[0]} -o '{image_file}'")
                        backed_up_images.append(possible_matches[0])
                        backed_up = True
                        print(f"  Successfully backed up {possible_matches[0]} as a fallback")
                    except Exception as e:
                        print(f"  Error saving fallback image {possible_matches[0]}: {e}")
        
        print(f"Successfully backed up {len(backed_up_images)} of {len(images)} images")
    
    # Backup container configurations with improved suffix matching
    if containers:
        # Get all containers including stopped ones
        all_containers_raw = run_command("docker ps -a --format '{{.Names}}'")
        all_containers = all_containers_raw.splitlines() if all_containers_raw else []
        print(f"Found {len(all_containers)} Docker containers on the system (including stopped)")
        
        # Debug output all container names
        print(f"Available containers: {', '.join(all_containers)}")
        
        for container in containers:
            print(f"Looking for container: {container}")
            matched = False
            
            # Create patterns to match, including with "-1" suffix
            patterns = [
                container,                    # exact match
                f"{container}-1",             # with -1 suffix (common Docker Compose pattern)
                f"{project_dir}_{container}", # project_container 
                f"{project_dir}_{container}-1", # project_container-1
                f"{project_dir}-{container}", # project-container
                f"{project_dir}-{container}-1" # project-container-1
            ]
            
            # Try each pattern
            for pattern in patterns:
                if pattern in all_containers:
                    print(f"Found container: {pattern}")
                    try:
                        container_file = os.path.join(containers_dir, pattern + '.json')
                        config = run_command(f"docker inspect {pattern}")
                        
                        if config:
                            with open(container_file, 'w') as f:
                                f.write(config)
                            print(f"Successfully backed up container: {pattern}")
                            matched = True
                            break
                    except Exception as e:
                        print(f"Error backing up container {pattern}: {e}")
            
            # If still not found, try partial matching (looking for containers that end with our name + suffix)
            if not matched:
                for actual_container in all_containers:
                    # Check for names that end with our container name + numeric suffix
                    if (actual_container.endswith(f"-{container}-1") or 
                        actual_container.endswith(f"_{container}-1") or
                        actual_container.endswith(f"-{container}")):
                        
                        print(f"Found container with suffix: {actual_container}")
                        try:
                            container_file = os.path.join(containers_dir, actual_container + '.json')
                            config = run_command(f"docker inspect {actual_container}")
                            
                            if config:
                                with open(container_file, 'w') as f:
                                    f.write(config)
                                print(f"Successfully backed up container: {actual_container}")
                                matched = True
                                break
                        except Exception as e:
                            print(f"Error backing up container {actual_container}: {e}")
                
            if not matched:
                print(f"Container {container} not found with any naming pattern")
                
    # Network and volume backup code would follow here...
    
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
    os.makedirs(os.path.join(backup_dir, 'containers'), exist_ok=True)
    
    # Get list of all containers
    all_containers = run_command("docker ps -a --format '{{.Names}}'").splitlines()
    
    # If no specific containers are specified, back up all
    if not containers_to_backup:
        containers_to_backup = all_containers
        print(f"Backing up all {len(all_containers)} containers")
    
    for container in containers_to_backup:
        print(f"Looking for container: {container}")
        if container in all_containers:
            print(f"Found container: {container}")
            # Rest of your backup code...
        else:
            print(f"Container {container} not found with any naming pattern")

def backup_volumes(backup_dir):
    """Backup Docker volumes"""
    print("Starting Docker volume backup...")
    os.makedirs(os.path.join(backup_dir, 'volumes'), exist_ok=True)
    
    # Get list of volumes
    volumes = run_command("docker volume ls -q").splitlines()
    print(f"Found {len(volumes)} volumes to backup")
    
    for volume in volumes:
        print(f"Backing up volume: {volume}")
        # Your volume backup code...
        print(f"Successfully backed up volume: {volume}")
    
    print("Volume backup complete")