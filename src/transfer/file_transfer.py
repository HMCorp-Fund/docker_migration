import os
import shutil
import subprocess
import zipfile
import tarfile
import ftplib  # Add this import for FTP support

def create_archive(archive_name, files):
    with zipfile.ZipFile(archive_name, 'w') as archive:
        for file in files:
            archive.write(file, os.path.basename(file))

def transfer_files(archive_path, destination):
    """
    Transfer files to a destination (local, remote via SCP, or FTP)
    
    Args:
        archive_path (str): Path to the archive file to transfer
        destination (str): Destination path (local, user@host:path for SCP, 
                          or ftp://user:pass@host/path for FTP)
        
    Returns:
        bool: True if successful, False otherwise
    """
    print(f"Transferring {archive_path} to {destination}")
    
    try:
        # FTP transfer (ftp://user:pass@host/path)
        if destination.startswith('ftp://'):
            print(f"Transferring via FTP to {destination}")
            
            # Parse FTP URL
            ftp_url = destination[6:]  # Remove 'ftp://'
            
            # Extract credentials and path
            if '@' in ftp_url:
                credentials, host_path = ftp_url.split('@', 1)
                if ':' in credentials:
                    username, password = credentials.split(':', 1)
                else:
                    username = credentials
                    password = input(f"Enter FTP password for {username}: ")
            else:
                host_path = ftp_url
                username = input("Enter FTP username: ")
                password = input("Enter FTP password: ")
            
            # Extract host and path
            if '/' in host_path:
                host, path = host_path.split('/', 1)
                path = '/' + path
            else:
                host = host_path
                path = '/'
            
            # Connect and transfer
            print(f"Connecting to FTP server {host}...")
            ftp = ftplib.FTP(host)
            ftp.login(username, password)
            
            # Change to destination directory or create if needed
            dirs = path.strip('/').split('/')
            for directory in dirs:
                if directory:
                    try:
                        ftp.cwd(directory)
                    except ftplib.error_perm:
                        ftp.mkd(directory)
                        ftp.cwd(directory)
            
            # Upload file
            filename = os.path.basename(archive_path)
            with open(archive_path, 'rb') as file:
                print(f"Uploading {filename}...")
                ftp.storbinary(f"STOR {filename}", file)
            
            ftp.quit()
            print(f"FTP transfer complete")
            return True
            
        # SCP transfer (user@host:path)
        elif ':' in destination and '@' in destination:
            # Remote transfer via SCP
            user_host, remote_path = destination.split(':', 1)
            print(f"Transferring to remote destination {user_host}:{remote_path}")
            
            # Execute SCP command
            scp_cmd = ["scp", archive_path, destination]
            print(f"Running: {' '.join(scp_cmd)}")
            
            result = subprocess.run(scp_cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"Error transferring file: {result.stderr}")
                return False
                
            print(f"Successfully transferred {archive_path} to {destination}")
            return True
        else:
            # Local file copy
            print(f"Copying to local destination {destination}")
            
            # Expand ~ if needed
            if destination.startswith('~'):
                destination = os.path.expanduser(destination)
            
            # Create destination directory if it doesn't exist
            os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
            
            # Copy file
            if os.path.isdir(destination):
                # If destination is a directory, copy file there with same name
                dest_path = os.path.join(destination, os.path.basename(archive_path))
            else:
                # Otherwise use destination as full path
                dest_path = destination
                
            shutil.copy2(archive_path, dest_path)
            print(f"Successfully copied {archive_path} to {dest_path}")
            return True
        
    except Exception as e:
        print(f"Error transferring file: {e}")
        return False

def main():
    # Example usage
    archive_name = 'docker_data.zip'
    files_to_archive = ['docker-compose.yml', 'other_file.txt']  # Replace with actual files
    create_archive(archive_name, files_to_archive)

    # Transfer the archive to the new server
    destination = 'user@new.server.com:~/path/to/destination/docker_data.zip'
    transfer_files(archive_name, destination)

if __name__ == "__main__":
    main()