import os
import sys
import subprocess

def get_directory_size(directory):
    total_size = 0
    for dirpath, _, filenames in os.walk(directory):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            total_size += os.path.getsize(fp)
    return total_size

def get_python_version(venv_path):
    python_executable = os.path.join(venv_path, 'bin', 'python')
    try:
        output = subprocess.check_output([python_executable, '--version'], stderr=subprocess.STDOUT)
        python_version = output.decode('utf-8').strip().split()[1]
        return ".".join(python_version.split(".")[:-1])
    except subprocess.CalledProcessError:
        return None

def get_package_size(venv_path):
    python_version = get_python_version(venv_path)
    if python_version is None:
        print("Error: Failed to determine Python version.")
        return

    package_dir = os.path.join(venv_path,  'lib', f"python{python_version}", 'site-packages')
    if not os.path.exists(package_dir):
        print("Error: Virtual environment does not exist or is not activated.")
        return

    total_size = get_directory_size(package_dir)
    return total_size

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python script.py /path/to/.venv")
        sys.exit(1)

    venv_path = sys.argv[1]
    total_package_size = get_package_size(venv_path)
    if total_package_size is not None:
        print(f"Total size of packages in virtual environment: {total_package_size / (1024*1024):.2f} MB")
