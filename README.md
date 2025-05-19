# Docker Migration Tool

## The Problem

Migrating Docker environments between servers can be challenging and error-prone. It involves multiple steps including backing up Docker data, transferring configurations, reinstalling services, and ensuring everything works correctly on the new server. This process is often manual, time-consuming, and requires specialized knowledge.

This tool solves this problem by automating the entire Docker migration workflow, reducing downtime, minimizing human error, and making migrations accessible even to those with limited Docker expertise.

## Features

- Identifies Docker images, containers, networks, and other related data from the Docker Compose file.
- Creates backups of Docker data and packages them into zip or tar files.
- Optionally includes additional host files specified in the Docker Compose file.
- Transfers the created archives to a new server via VPN.
- Extracts the archives and reinstalls Docker on the new server.
- Validates the running state of Docker services after installation.

## Project Structure

```
docker-migration-tool
├── src
│   ├── main.py                # Entry point of the application
│   ├── docker_utils           # Package for Docker utilities
│   │   ├── __init__.py
│   │   ├── compose_parser.py   # Parses Docker Compose files
│   │   └── docker_backup.py    # Handles Docker data backup
│   ├── archive                # Package for archiving utilities
│   │   ├── __init__.py
│   │   ├── archiver.py        # Creates and combines archives
│   │   └── extractor.py       # Extracts archives on the new server
│   ├── transfer               # Package for file transfer utilities
│   │   ├── __init__.py
│   │   └── file_transfer.py    # Transfers files via VPN
│   └── validation             # Package for validation utilities
│       ├── __init__.py
│       └── health_check.py     # Checks Docker service health
├── requirements.txt           # Project dependencies
├── setup.py                   # Packaging configuration
├── README.md                  # Project documentation
└── .gitignore                 # Git ignore file
```

## Installation

### Via pip

The simplest way to install the Docker Migration Tool is via pip:

```
pip install docker-migration
```

This will install the tool and all its dependencies. After installation, you can use the `docker-migration` command from anywhere.

### Using a virtual environment (recommended)

For a clean installation isolated from system packages:

```bash
# Install virtualenv if needed
sudo apt-get update
sudo apt-get install -y python3-venv

# Create and activate a virtual environment
cd ~
python3 -m venv docker_migration_env
source docker_migration_env/bin/activate

# Install in the virtual environment
pip install docker-migration

# Test the command
docker-migration --help
```

### From Source

Install the package:
   ```
   pip install docker-migration
   ```

## Usage

### Basic Usage

1. Navigate to the directory containing your Docker Compose file.
2. Run the migration tool:
   ```
   docker-migration
   ```

   Or if installed from source:
   ```
   python src/main.py
   ```
3. Follow the prompts to complete the migration process.

### Advanced Options

#### Backup Mode
```
docker-migration --mode backup [options]
```

Options:
- `--backup-all`: Backup all Docker resources on the server instead of just those in docker-compose.yml
- `--docker-src-base-dir PATH`: Include a specific directory containing Docker source files in the backup
- `--skip-images`: Skip backing up Docker images (which can be large)
- `--skip-containers`: Skip backing up Docker containers
- `--config-only`: Only backup configurations (equivalent to using both --skip-images and --skip-containers)
- `--pull-images`: Pull Docker images defined in docker-compose.yml before backup
- `--transfer`: Transfer the backup to another location
- `--destination PATH`: Specify destination path (local path, user@host:/path for SCP, or ftp://user:pass@host/path for FTP)
- `--ftp-user USERNAME`: FTP username (if not specified in destination)
- `--ftp-pass PASSWORD`: FTP password (if not specified in destination)
- `--no-prompt`: Do not prompt for user input (automatically include current directory in backup)

#### Restore Mode
```
docker-migration --mode restore --backup-file PATH [options]
```

Options:
- `--backup-file PATH`: Path to backup file (required for restore mode)
- `--compose-file-path PATH`: Path to docker-compose.yml file for restoration
- `--extract-only`: Extract files without restoring Docker components
- `--target-dir PATH`: Directory to extract application files to (for extract-only mode)

## Use Cases

1. **Server Migration**: Migrate a complete Docker environment from one server to another.
2. **Environment Backup**: Create a backup of your Docker environment before making significant changes.
3. **Disaster Recovery**: Restore Docker services quickly after a system failure.
4. **Dev/Test Cloning**: Clone a production environment to development or testing servers.
5. **Configuration Extraction**: Extract only configuration files without the Docker images for lightweight backups.
6. **Selective Migration**: Migrate specific components of your Docker environment by using skip options.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.