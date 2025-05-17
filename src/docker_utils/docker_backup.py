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
    
    # Save container details
    containers_json = []
    existing_containers = []
    
    # First check which containers actually exist
    for container_id in containers:
        container_info = run_command(f"docker inspect {container_id}")
        if container_info:
            try:
                containers_json.append(json.loads(container_info)[0])
                existing_containers.append(container_id)
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
        # Fix permissions on the saved image file - make sure we use sudo too
        run_command(f"chmod 644 '{image_filename}'", capture_output=False, use_sudo=True)
    
    # Save networks - add same error handling as containers
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
    
    # Update networks list to only include existing ones
    networks = existing_networks
    
    # Create a manifest file with metadata
    with open(os.path.join(backup_dir, 'manifest.json'), 'w') as f:
        json.dump({
            'images': images,
            'containers': containers,
            'networks': networks,
            'date': str(datetime.datetime.now()),
            'docker_version': run_command("docker version --format '{{.Server.Version}}'")
        }, f, indent=2)
    
    # Fix permissions on the entire backup directory - make sure we use sudo
    run_command(f"chmod -R a+r '{backup_dir}'", capture_output=False, use_sudo=True)
    
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
    
    # Look for inner Docker backup archive
    docker_backup_tar = None
    for file in os.listdir(extract_dir):
        if file.startswith('docker_backup_') and file.endswith('.tar'):
            docker_backup_tar = os.path.join(extract_dir, file)
            break
    
    if docker_backup_tar:
        print(f"Found inner Docker backup archive: {docker_backup_tar}")
        # Extract the inner Docker backup archive
        docker_extract_dir = os.path.join(extract_dir, "docker_data")
        os.makedirs(docker_extract_dir, exist_ok=True)
        
        with tarfile.open(docker_backup_tar, 'r:*') as tar:
            tar.extractall(path=docker_extract_dir)
            
        # Find the docker_backup_ directory inside the extracted content
        for item in os.listdir(docker_extract_dir):
            item_path = os.path.join(docker_extract_dir, item)
            if os.path.isdir(item_path) and item.startswith('docker_backup_'):
                return item_path
    
        # If we couldn't find a docker_backup_ directory, return the extraction directory
        return docker_extract_dir
    else:
        print(f"Warning: Could not find docker_backup_*.tar file in the archive")
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
    
    for network_file in os.listdir(networks_dir):
        if network_file.endswith('.json'):
            network_path = os.path.join(networks_dir, network_file)
            network_name = os.path.splitext(network_file)[0]
            
            with open(network_path, 'r') as f:
                network_config = json.load(f)
            
            # Check if network already exists
            check_result = run_command(f"docker network ls --format '{{{{.Name}}}}' --filter name=^{network_name}$")
            if check_result and network_name in check_result.splitlines():
                print(f"Network {network_name} already exists, skipping creation")
                restored_networks.append(network_name)
                continue
            
            # Get network driver
            driver = network_config.get('Driver', 'bridge')
            
            # Create network with basic options
            print(f"Creating network: {network_name} with driver {driver}")
            result = run_command(f"docker network create --driver {driver} {network_name}")
            
            if result:
                restored_networks.append(network_name)
                print(f"Successfully created network: {network_name}")
    
    print(f"Restored {len(restored_networks)} Docker networks")
    return restored_networks


def restore_containers(backup_dir, networks):
    """
    Restore Docker containers from backup
    
    Args:
        backup_dir (str): Path to the extracted backup directory
        networks (list): List of available networks
        
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
            if source and target:
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
    Restore a Docker backup
    
    Args:
        backup_file (str): Path to the backup file
        extract_dir (str, optional): Directory to extract to
        
    Returns:
        tuple: (restored_images, restored_networks, restored_containers)
    """
    print(f"Starting Docker restoration from {backup_file}")
    
    # Extract the backup
    backup_dir = extract_backup(backup_file, extract_dir)
    
    # Restore Docker components in the correct order
    restored_images = restore_images(backup_dir)
    restored_networks = restore_networks(backup_dir)
    restored_containers = restore_containers(backup_dir, restored_networks)
    
    print(f"\nDocker restoration complete!")
    print(f"Restored {len(restored_images)} images, {len(restored_networks)} networks, and {len(restored_containers)} containers")
    
    return (restored_images, restored_networks, restored_containers)


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