import os
import yaml # type: ignore

def parse_compose_file(compose_file_path):
    """
    Parse a Docker Compose file to identify resources
    
    Args:
        compose_file_path (str): Path to the docker-compose.yml file
        
    Returns:
        tuple: (images, containers, networks, additional_files)
    """
    print(f"Parsing Docker Compose file: {compose_file_path}")
    
    try:
        with open(compose_file_path, 'r') as f:
            compose_data = yaml.safe_load(f)
        
        images = []
        containers = []
        networks = []
        additional_files = []
        
        # Process services
        if 'services' in compose_data:
            for service_name, service_config in compose_data['services'].items():
                # Get image
                if 'image' in service_config:
                    images.append(service_config['image'])
                
                # Get container name if specified
                if 'container_name' in service_config:
                    containers.append(service_config['container_name'])
                else:
                    # If container name not specified, Docker Compose generates one
                    containers.append(f"{os.path.basename(os.getcwd())}_{service_name}")
                
                # Check for volumes that might point to external files
                if 'volumes' in service_config:
                    for volume in service_config['volumes']:
                        if ':' in volume:
                            host_path = volume.split(':')[0]
                            if os.path.exists(host_path) and os.path.isfile(host_path):
                                additional_files.append(host_path)
        
        # Process networks
        if 'networks' in compose_data:
            for network_name in compose_data['networks']:
                networks.append(network_name)
        
        print(f"Found {len(images)} images, {len(containers)} containers, {len(networks)} networks, and {len(additional_files)} additional files")
        return images, containers, networks, additional_files
        
    except Exception as e:
        print(f"Error parsing Docker Compose file: {e}")
        return [], [], [], []

def main():
    compose_file_path = 'docker-compose.yml'
    images, containers, networks, additional_files = parse_compose_file(compose_file_path)
    print({
        'images': images,
        'containers': containers,
        'networks': networks,
        'additional_files': additional_files
    })

if __name__ == "__main__":
    main()