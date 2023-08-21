# Use a Windows base image
FROM mcr.microsoft.com/windows/servercore:ltsc2019

ARG USERNAME=kerrigan
ARG USER_UID=1000
ARG USER_GID=$USER_UID

SHELL ["powershell", "-Command", "$ErrorActionPreference = 'Stop'; $ProgressPreference = 'SilentlyContinue';"]

RUN New-LocalUser -Name $env:USERNAME -Password (ConvertTo-SecureString -AsPlainText 'Password123' -Force) `
    -FullName 'Kerrigan' -Description 'Docker User' -NoPasswordExpiration

RUN Add-LocalGroupMember -Group administrators -Member $env:USERNAME

# Install software
RUN Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.10.0/python-3.10.0-amd64.exe' -OutFile 'python-installer.exe'; `
    Start-Process -Wait -FilePath 'python-installer.exe' -ArgumentList '/quiet InstallAllUsers=1 PrependPath=1'; `
    Remove-Item -Force 'python-installer.exe'

RUN Invoke-WebRequest -Uri 'https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py' -OutFile 'get-poetry.py'; `
    python get-poetry.py; `
    Remove-Item -Force 'get-poetry.py'

RUN [Environment]::SetEnvironmentVariable('Path', $env:Path + ';%APPDATA%\Python\Scripts', [EnvironmentVariableTarget]::Machine)

WORKDIR C:\Users\$env:USERNAME
