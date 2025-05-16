import os
import subprocess
import yaml # type: ignore
import time

def check_docker_services():
    """
    Check if Docker services are running properly
    
    Returns:
        bool: True if all services are running, False otherwise
    """
    print("Checking Docker services status...")
    
    # First check if Docker daemon is running
    try:
        result = subprocess.run(["docker", "info"], 
                               capture_output=True, text=True, check=False)
        if result.returncode != 0:
            print("Docker daemon is not running!")
            print(result.stderr)
            return False
        
        print("Docker daemon is running.")
    except Exception as e:
        print(f"Error checking Docker daemon: {e}")
        return False
    
    # Check if docker-compose.yml exists
    compose_file = 'docker-compose.yml'
    if os.path.exists(compose_file):
        print(f"Found {compose_file}. Checking services defined in it...")
        
        try:
            # Check docker-compose services
            result = subprocess.run(["docker-compose", "ps", "--services"], 
                                  capture_output=True, text=True, check=False)
            
            if result.returncode != 0:
                print(f"Error running docker-compose ps: {result.stderr}")
                return False
            
            services = result.stdout.strip().split('\n')
            if not services or services[0] == '':
                print("No services found in docker-compose.yml or they are not running.")
                return False
            
            # Get status of each service
            all_running = True
            for service in services:
                if not service:  # Skip empty lines
                    continue
                    
                svc_result = subprocess.run(
                    ["docker-compose", "ps", "--services", "--filter", f"status=running", service],
                    capture_output=True, text=True, check=False
                )
                
                if service not in svc_result.stdout:
                    print(f"Service {service} is not running!")
                    all_running = False
                else:
                    print(f"Service {service} is running.")
            
            return all_running
            
        except Exception as e:
            print(f"Error checking docker-compose services: {e}")
            return False
    else:
        print("No docker-compose.yml found. Checking for running Docker containers...")
        
        # Just check if there are any running containers
        try:
            result = subprocess.run(["docker", "ps", "--format", "{{.Names}}"], 
                                   capture_output=True, text=True, check=False)
            
            if result.returncode != 0:
                print(f"Error checking Docker containers: {result.stderr}")
                return False
            
            containers = result.stdout.strip().split('\n')
            if not containers or containers[0] == '':
                print("No running Docker containers found.")
                return False
            
            print(f"Found {len(containers)} running containers:")
            for container in containers:
                if container:  # Skip empty lines
                    print(f" - {container}")
            
            return True
            
        except Exception as e:
            print(f"Error checking Docker containers: {e}")
            return False

def wait_for_services(timeout=60):
    """
    Wait for all Docker services to be in a running state
    
    Args:
        timeout (int): Maximum time to wait in seconds
        
    Returns:
        bool: True if all services are running, False if timeout
    """
    print(f"Waiting for Docker services to start (timeout: {timeout}s)...")
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        if check_docker_services():
            return True
        
        print(f"Not all services running yet. Waiting for 5 seconds...")
        time.sleep(5)
    
    print(f"Timeout of {timeout}s reached waiting for services to start.")
    return False

if __name__ == "__main__":
    check_docker_services()