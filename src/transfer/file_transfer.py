import os
import paramiko # type: ignore
import zipfile
import tarfile

def create_archive(archive_name, files):
    with zipfile.ZipFile(archive_name, 'w') as archive:
        for file in files:
            archive.write(file, os.path.basename(file))

def transfer_file(local_path, remote_path, hostname, username, password):
    try:
        transport = paramiko.Transport((hostname, 22))
        transport.connect(username=username, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        sftp.put(local_path, remote_path)
        sftp.close()
        transport.close()
    except Exception as e:
        print(f"Error transferring file: {e}")

def main():
    # Example usage
    archive_name = 'docker_data.zip'
    files_to_archive = ['docker-compose.yml', 'other_file.txt']  # Replace with actual files
    create_archive(archive_name, files_to_archive)

    # Transfer the archive to the new server
    hostname = 'new.server.com'
    username = 'user'
    password = 'password'
    remote_path = f'~/path/to/destination/{archive_name}'
    transfer_file(archive_name, remote_path, hostname, username, password)

if __name__ == "__main__":
    main()