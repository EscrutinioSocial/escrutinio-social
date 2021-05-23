FROM python:3.7-slim
ENV PYTHONUNBUFFERED 1

RUN apt-get update 
RUN apt-get install -y --no-install-recommends \
    build-essential \
    zlib1g-dev \
    libjpeg-dev \
    binutils \
    git \
    libproj-dev \
    wget \
    libmagic1 \
    gdal-bin

WORKDIR /src
COPY . .

RUN pip install -U pip
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements.txt

CMD ["gunicorn", "escrutinio_social.wsgi"]
