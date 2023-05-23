"""Tunnel utilities."""
import os
import platform
import re
import socket
import subprocess
import tarfile
import time
import zipfile

import requests
from pydantic import BaseModel
from rich import print

file_list = {
    ("Darwin", "x86_64"): "darwin_amd64.tar.gz",
    ("Darwin", "arm64"): "darwin_arm64.tar.gz",
    ("FreeBSD", "i386"): "freebsd_386.tar.gz",
    ("FreeBSD", "x86_64"): "freebsd_amd64.tar.gz",
    ("Linux", "i386"): "linux_386.tar.gz",
    ("Linux", "x86_64"): "linux_amd64.tar.gz",
    ("Linux", "arm"): "linux_arm.tar.gz",
    ("Linux", "arm64"): "linux_arm64.tar.gz",
    ("Linux", "mips"): "linux_mips.tar.gz",
    ("Linux", "mips64"): "linux_mips64.tar.gz",
    ("Linux", "mips64le"): "linux_mips64le.tar.gz",
    ("Linux", "mipsle"): "linux_mipsle.tar.gz",
    ("Linux", "riscv64"): "linux_riscv64.tar.gz",
    ("Windows", "i386"): "windows_386.zip",
    ("Windows", "x86_64"): "windows_amd64.zip",
    ("Windows", "arm64"): "windows_arm64.zip",
}


def remove_file_extensions(input_string: str) -> str:
    """Remove file extensions from a string.


    Args:
        input_string: The string to remove file extensions from.

    Returns:
        The string with file extensions removed.
    """
    pattern = r"(\.tar\.gz|\.zip)"
    return re.sub(pattern, "", input_string)


def is_port_in_use(ip: str, port: int) -> bool:
    """Check if a port is in use.

    Args:
        ip: The IP address to check.
        port: The port to check.

    Returns:
        True if the port is in use, False otherwise.
    """
    sock = None  # Initialize sock variable

    try:
        # Create a socket object
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Try to connect to the specified port
        result = sock.connect_ex((ip, port))
        return result == 0
    except socket.error as e:
        print(f"Error occurred while checking port: {e}")
        return False
    finally:
        # Close the socket if it has been initialized
        if sock:
            sock.close()


def find_unused_ports(ip_address, start_port, end_port, num_ports) -> list[int]:
    """Find unused ports in a range.

    Args:
        ip_address: The IP address to check.
        start_port: The start of the port range.
        end_port: The end of the port range.
        num_ports: The number of unused ports to find.


    Returns:
        A list of unused ports.
    """
    unused_ports = []

    for i in range(start_port, end_port):
        if not is_port_in_use(ip_address, i):
            unused_ports.append(i)
            if len(unused_ports) == num_ports:
                # Stop iterating once the desired number of unused ports is found
                break

    return unused_ports


class Tunnel(BaseModel):
    """Tunnel class."""

    ip: str = "3.101.35.30"
    frp_version: str = "0.48.0"
    file_name: str = ""
    backend_remote_port: int = 0
    frontend_remote_port: int = 0
    backend_local_port: int = 8000
    frontend_local_port: int = 3000
    timeout: int = 3000

    def get_backend_url(self) -> str:
        """Get the backend URL.


        Returns:
            The backend URL.
        """
        return f"http://{self.ip}:{self.backend_remote_port}"

    def download_and_uncompress_frp(self):
        """Download and uncompress frp.


        Raises:
            ValueError: If the OS or architecture is not supported.
            ValueError: If the file format is not supported.
        """
        base_url = (
            f"https://github.com/fatedier/frp/releases/download/v{self.frp_version}/"
        )
        os_name = platform.system()
        arch = platform.machine()

        if arch == "AMD64":
            arch = "x86_64"

        value = file_list.get((os_name, arch))  # type: ignore
        if value is not None:
            self.file_name = value
        else:
            raise ValueError(
                f"Unsupported OS or architecture for preview: {os_name} {arch}"
            )

        file_url = base_url + f"frp_{self.frp_version}_{self.file_name}"
        response = requests.get(file_url)

        if response.status_code == 200:
            with open(self.file_name, "wb") as f:
                f.write(response.content)
        else:
            raise ValueError(f"Failed to download file: {file_url}")

        if self.file_name.endswith(".tar.gz"):
            with tarfile.open(self.file_name, "r:gz") as tar:
                tar.extractall()
        elif self.file_name.endswith(".zip"):
            with zipfile.ZipFile(self.file_name, "r") as zip_ref:
                zip_ref.extractall()
        else:
            raise ValueError(f"Unsupported file format: {self.file_name}")

    def generate_frpc_ini(self):
        """Generate frpc.ini."""
        ports = find_unused_ports(self.ip, 8001, 8100, 2)
        self.backend_remote_port = ports[0]
        self.frontend_remote_port = ports[1]

        frpc_ini_content = f"""[common]
server_addr = {self.ip}
server_port = 8000

[web_app_backend]
type = tcp
local_ip = 127.0.0.1
local_port = {self.backend_local_port}
remote_port = {self.backend_remote_port}

[web_app_frontend]
type = tcp
local_ip = 127.0.0.1
local_port = {self.frontend_local_port}
remote_port = {self.frontend_remote_port}
"""
        output_file_path = f"./frp_{self.frp_version}_{remove_file_extensions(self.file_name)}/frpc.ini"
        with open(output_file_path, "w") as f:
            f.write(frpc_ini_content)

    def run_frpc_with_ini(self):
        """Run frpc with frpc.ini.


        Raises:
            ValueError: If the frpc executable or frpc.ini file is not found.

        Returns:
            The path to the log file.

        """
        frpc_executable = (
            f"./frp_{self.frp_version}_{remove_file_extensions(self.file_name)}/frpc"
        )
        frpc_ini_path = f"./frp_{self.frp_version}_{remove_file_extensions(self.file_name)}/frpc.ini"
        # Check if the frpc_executable file exists
        if not os.path.exists(frpc_executable):
            raise ValueError(
                f"{frpc_executable} not found. Please provide a valid file path."
            )

        # Check if the frpc.ini file exists
        if not os.path.exists(frpc_ini_path):
            raise ValueError(
                f"{frpc_ini_path} not found. Please provide a valid file path."
            )

        log_file_path = f"./frp_{self.frp_version}_{remove_file_extensions(self.file_name)}/frpc.log"  # Update this path if you want to store the log file elsewhere
        with open(log_file_path, "w") as log_file:
            process = subprocess.Popen(
                [frpc_executable, "-c", frpc_ini_path],
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )

            start_time = time.time()
            print(
                f"[bold blue]Pynecone Preview Url:[/bold blue] [green]http://{self.ip}:{self.frontend_remote_port}[/green]"
            )
            try:
                while time.time() - start_time < self.timeout:
                    if (
                        process.poll() is not None
                    ):  # Check if the process has terminated
                        break
                    time.sleep(1)  # Wait for 1 second before checking again
            except KeyboardInterrupt:
                return

            if process.poll() is None:  # Check if the process is still running
                process.terminate()

            return_code = process.returncode
            if return_code != 0:
                print(
                    f"PC Preview Timeout. Please Run [bold blue]pynecone preview[/bold blue] again."
                )
