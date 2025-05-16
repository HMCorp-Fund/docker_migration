import os
import yaml # type: ignore

def parse_docker_compose(compose_file='docker-compose.yml'):
    if not os.path.exists(compose_file):
        raise FileNotFoundError(f"{compose_file} not found.")
    
    with open(compose_file, 'r') as file:
        compose_data = yaml.safe_load(file)

    services = compose_data.get('services', {})
    images = set()
    containers = set()
    networks = set()
    volumes = set()

    for service_name, service in services.items():
        if 'image' in service:
            images.add(service['image'])
        if 'networks' in service:
            networks.update(service['networks'].keys())
        if 'volumes' in service:
            volumes.update(service['volumes'])

        containers.add(service_name)

    return {
        'images': list(images),
        'containers': list(containers),
        'networks': list(networks),
        'volumes': list(volumes),
        'additional_files': get_additional_files(compose_data)
    }

def get_additional_files(compose_data):
    additional_files = []
    for service in compose_data.get('services', {}).values():
        if 'volumes' in service:
            for volume in service['volumes']:
                if isinstance(volume, str):
                    additional_files.append(volume.split(':')[0])  # Get host path
                elif isinstance(volume, dict) and 'source' in volume:
                    additional_files.append(volume['source'])
    return list(set(additional_files))  # Remove duplicates

def main():
    docker_data = parse_docker_compose()
    print(docker_data)

if __name__ == "__main__":
    main()