# Simple Docker example to clone and run an app.
# docker build . -t pynecone-app
# docker run -p 3000:3000 -p 8000:8000 pynecone-app pc run

FROM ubuntu

# Install dependencies.
RUN apt-get update && apt-get install -y \
    git \
    python3-dev \
    python3-pip \
    nodejs \
    curl \
    unzip

# Install pynecone
RUN pip install pynecone

# Clone your code.
RUN git clone https://github.com/pynecone-io/pynecone-examples.git

# Initialize your app.
RUN cd pynecone-examples/snakegame; pip install -r requirements.txt; pc init;

# Set the working directory.
WORKDIR pynecone-examples/snakegame
