def check_docker_services_running():
    import subprocess

    try:
        # Get the status of all Docker services
        result = subprocess.run(['docker', 'ps'], capture_output=True, text=True)

        # Check if the command was successful
        if result.returncode != 0:
            print("Error checking Docker services:", result.stderr)
            return False

        # Check if there are any running services
        if "CONTAINER ID" in result.stdout:
            print("Docker services are running:")
            print(result.stdout)
            return True
        else:
            print("No Docker services are currently running.")
            return False

    except Exception as e:
        print("An error occurred while checking Docker services:", str(e))
        return False