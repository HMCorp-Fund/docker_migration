# Docker Migration Tool

This project provides a comprehensive solution for migrating Docker environments using Docker Compose. It automates the process of preparing Docker data, creating archives, transferring files to a new server, and reinstalling Docker on the new server.

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

1. Clone the repository:
   ```
   git clone <repository-url>
   cd docker-migration-tool
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Navigate to the directory containing your Docker Compose file.
2. Run the migration tool:
   ```
   python src/main.py
   ```

Follow the prompts to complete the migration process.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.