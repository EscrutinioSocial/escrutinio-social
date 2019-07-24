FROM python:3.7-slim
ENV PYTHONUNBUFFERED 1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    zlib1g-dev \
    libjpeg-dev \
    binutils \
    git \
    libproj-dev \
    wget \
    gdal-bin && rm -rf /var/lib/apt/lists/*

#RUN mkdir /src
WORKDIR /src
#ADD requirements.txt /src/
#ADD requirements /src/requirements
ADD . /src/
RUN pip install -r requirements.txt

EXPOSE 8000
CMD ["bash", "entrypoint.sh"]
