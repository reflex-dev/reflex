FROM python:3.8-slim-buster

RUN pip install --upgrade pip

RUN apt-get update

RUN apt-get install curl unzip --yes

RUN apt-get update && apt-get install -y nodejs npm
RUN curl -fsSL https://deb.nodesource.com/setup_16.x | bash - && apt-get install -y nodejs

RUN python3 -m venv /opt/venv

RUN . /opt/venv/bin/activate

RUN pip install pynecone-io

WORKDIR /pynecone

RUN mkdir demo_pynecone_app

WORKDIR /pynecone/demo_pynecone_app

RUN pc init

CMD ["pc","run"]

EXPOSE 3000
EXPOSE 8000

