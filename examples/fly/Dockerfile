FROM ubuntu/redis

# Non-interactive mode.
ENV DEBIAN_FRONTEND=noninteractive

# Install dependencies.
RUN apt update && apt install -y \
    build-essential \
    curl \
    unzip \
    git \
    sudo 

RUN sudo apt install -y software-properties-common 
RUN sudo add-apt-repository ppa:deadsnakes/ppa
RUN sudo apt-get update
RUN sudo apt install -y python3.11

RUN sudo apt-get install -y python3-distutils

RUN sudo apt-get install -y python3-apt

RUN sudo apt install -y libpq-dev python3-dev

# Install poetry.
RUN python3 --version
RUN curl -sSL https://install.python-poetry.org | python3 - --git https://github.com/python-poetry/poetry.git@master
ENV PATH="/root/.local/bin:$PATH"
RUN poetry --version

# Add poetry to the path.
ENV PATH="$PATH:/root/.poetry/bin"
RUN poetry --version

# Install dependencies.
RUN mkdir project
WORKDIR /project

# Copy the project from s3
COPY ./run.sh  /run.sh 

# ARG for the counter directory
ARG PROJ_DIR

# Set the PROJ_DIR environment variable
ENV PROJ_DIR=${PROJ_DIR}

# Copy Project Folder
COPY ./${PROJ_DIR} ${PROJ_DIR}
COPY ./config_setup.py  ${PROJ_DIR}/config_setup.py

EXPOSE 8000

RUN chmod +x /run.sh
ENTRYPOINT ["/run.sh"]