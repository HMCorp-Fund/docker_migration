def create_docker_backup(backup_dir, include_current_dir=False):
    import os
    import tarfile
    import docker # type: ignore

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
    import shutil

    # Transfer the backup file to the new server
    shutil.copy(backup_file, destination)


def main():
    backup_dir = './__docker_backup'
    backup_file = create_docker_backup(backup_dir, include_current_dir=True)
    transfer_backup(backup_file, '~/docker_backups')


if __name__ == "__main__":
    main()