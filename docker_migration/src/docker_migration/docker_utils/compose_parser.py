import os
import yaml # type: ignore

def parse_compose_file(compose_file):
    """
    Parse a docker-compose.yml file and extract images, containers, networks, and volumes
    
    Args:
        compose_file (str): Path to docker-compose.yml file
        
    Returns:
        tuple: (images, containers, networks, volumes, additional_files)
    """
    try:
        import yaml # type: ignore
        with open(compose_file, 'r') as f:
            compose_data = yaml.safe_load(f)
        
        if not compose_data:
            print(f"Warning: Empty or invalid docker-compose.yml file: {compose_file}")
            return [], [], [], [], [compose_file]
        
        # Extract images
        images = []
        containers = []
        additional_files = []
        
        if 'services' in compose_data and compose_data['services']:
            for service_name, service in compose_data['services'].items():
                if isinstance(service, dict) and 'image' in service:
                    images.append(service['image'])
                    
                    # Add container name, considering multiple naming patterns
                    if 'container_name' in service:
                        # Explicit container name
                        containers.append(service['container_name'])
                    else:
                        # Try Docker Compose default naming patterns
                        project_name = os.path.basename(os.path.dirname(os.path.abspath(compose_file)))
                        
                        # Standard Docker Compose pattern (project_service)
                        containers.append(f"{project_name}_{service_name}")
                        
                        # Alternative pattern with hyphens (project-service-1)
                        containers.append(f"{project_name}-{service_name}")
                        
                        # Just the service name (for flexibility)
                        containers.append(service_name)
        else:
            print(f"Warning: No services found in docker-compose.yml")
        
        # Extract networks
        networks = []
        if 'networks' in compose_data and compose_data['networks']:
            if isinstance(compose_data['networks'], dict):
                networks = list(compose_data['networks'].keys())
                
                # For external networks, try to get the actual name
                for network_name, network in compose_data['networks'].items():
                    if isinstance(network, dict) and 'external' in network:
                        if isinstance(network['external'], dict) and 'name' in network['external']:
                            networks.append(network['external']['name'])
                        elif network['external'] is True and 'name' in network:
                            networks.append(network['name'])
        
        # Extract volumes
        volumes = []
        if 'volumes' in compose_data and compose_data['volumes']:
            if isinstance(compose_data['volumes'], dict):
                volumes = list(compose_data['volumes'].keys())
                
                # For external volumes, try to get the actual name
                for volume_name, volume in compose_data['volumes'].items():
                    if isinstance(volume, dict) and 'external' in volume:
                        if isinstance(volume['external'], dict) and 'name' in volume['external']:
                            volumes.append(volume['external']['name'])
                        elif volume['external'] is True and 'name' in volume:
                            volumes.append(volume['name'])
        
        # Add environment files to additional files list
        if 'services' in compose_data:
            for service_name, service in compose_data['services'].items():
                if isinstance(service, dict) and 'env_file' in service:
                    if isinstance(service['env_file'], list):
                        for env_file in service['env_file']:
                            additional_files.append(env_file)
                    else:
                        additional_files.append(service['env_file'])
        
        # Add the compose file itself to additional files
        additional_files.append(compose_file)
        
        return images, containers, networks, volumes, additional_files
        
    except Exception as e:
        print(f"Error parsing docker-compose file: {e}")
        return [], [], [], [], [compose_file]

def main():
    compose_file_path = 'docker-compose.yml'
    images, containers, networks, volumes, additional_files = parse_compose_file(compose_file_path)
    print({
        'images': images,
        'containers': containers,
        'networks': networks,
        'volumes': volumes,
        'additional_files': additional_files
    })

if __name__ == "__main__":
    main()