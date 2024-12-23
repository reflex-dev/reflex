FROM python:3.9

ARG USERNAME=kerrigan
RUN useradd -m $USERNAME
RUN apt-get update && apt-get install -y redis && rm -rf /var/lib/apt/lists/*
USER $USERNAME

WORKDIR /home/$USERNAME
