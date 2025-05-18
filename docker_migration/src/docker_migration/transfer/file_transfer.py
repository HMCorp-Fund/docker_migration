import os
import shutil
import subprocess
import zipfile
import tarfile

def create_archive(archive_name, files):
    with zipfile.ZipFile(archive_name, 'w') as archive:
        for file in files:
            archive.write(file, os.path.basename(file))

def transfer_files(file_path, destination):
    """
    Transfer files to another server or location
    
    Args:
        file_path (str): Path to the file to transfer
        destination (str): Destination (local path, SCP path, or FTP URL)
    """
    filename = os.path.basename(file_path)
    filesize = os.path.getsize(file_path)
    
    # Format filesize for display
    def format_size(size):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    
    print(f"Transferring {filename} ({format_size(filesize)}) to {destination}")
    
    try:
        if ':' in destination and not destination.startswith('ftp://'):  # SCP transfer
            # SCP transfer code (unchanged)
            username, host_path = destination.split(':', 1)
            host, remote_path = host_path.split('/', 1)
            remote_path = '/' + remote_path
            
            print(f"Transferring via SCP to {username}@{host}:{remote_path}")
            subprocess.run(['scp', file_path, f"{username}@{host}:{remote_path}"], check=True)
            print("SCP transfer complete")
            
        elif destination.startswith('ftp://'):  # FTP transfer
            from ftplib import FTP
            import time
            
            # Parse FTP URL for credentials
            ftp_url = destination[6:]  # Remove 'ftp://'
            if '@' in ftp_url:
                creds, host_path = ftp_url.split('@', 1)
                if ':' in creds:
                    username, password = creds.split(':', 1)
                else:
                    username, password = creds, ''
            else:
                username, password = 'anonymous', ''
                host_path = ftp_url
            
            if '/' in host_path:
                host, remote_path = host_path.split('/', 1)
                remote_path = '/' + remote_path
            else:
                host, remote_path = host_path, '/'
            
            print(f"Transferring via FTP to ftp://{username}:{'*'*len(password)}@{host}")
            print(f"Connecting to FTP server {host}...")
            
            # Set up FTP connection with timeout
            ftp = FTP(host, timeout=60)
            ftp.login(username, password)
            
            # Create a callback function to show progress
            uploaded = 0
            start_time = time.time()
            last_update = start_time
            
            def upload_callback(buffer):
                nonlocal uploaded, last_update
                uploaded += len(buffer)
                percent = (uploaded / filesize) * 100
                current_time = time.time()
                
                # Update progress every second
                if current_time - last_update > 1:
                    elapsed = current_time - start_time
                    speed = uploaded / elapsed if elapsed > 0 else 0
                    eta = (filesize - uploaded) / speed if speed > 0 else 0
                    
                    print(f"\rProgress: {percent:.1f}% | {format_size(uploaded)}/{format_size(filesize)} | "
                          f"{format_size(speed)}/s | ETA: {int(eta/60):02d}:{int(eta%60):02d}", end='', flush=True)
                    last_update = current_time
            
            # Upload the file with progress reporting
            with open(file_path, 'rb') as file:
                print(f"Uploading {filename}...")
                ftp.storbinary(f"STOR {filename}", file, blocksize=8192, callback=upload_callback)
            
            print("\nFTP transfer complete")
            ftp.quit()
            
        else:  # Local file copy
            os.makedirs(os.path.dirname(os.path.join(destination, filename)), exist_ok=True)
            shutil.copy(file_path, os.path.join(destination, filename))
            print(f"File copied to {os.path.join(destination, filename)}")
            
    except Exception as e:
        print(f"Error transferring file: {e}")
        raise

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