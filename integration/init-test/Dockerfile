FROM ubuntu:latest

ARG USERNAME=kerrigan
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    #
    # [Optional] Add sudo support. Omit if you don't need to install software after connecting.
    && apt-get update \
    && apt-get install -y sudo curl xz-utils python3 python3-pip python3.10-venv unzip \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

USER $USERNAME

RUN curl -sSL https://install.python-poetry.org | python3 -
RUN sudo ln -s /home/$USERNAME/.local/bin/poetry /usr/local/bin/poetry

WORKDIR /home/$USERNAME
