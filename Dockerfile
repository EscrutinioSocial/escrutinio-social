FROM python:3.7-slim

# This prevents Python from writing out pyc files
ENV PYTHONDONTWRITEBYTECODE 1

# This keeps Python from buffering stdin/stdout
ENV PYTHONUNBUFFERED 1

ARG DEBIAN_FRONTEND=noninteractive

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
    gdal-bin \
    poppler-utils \
    htop

RUN python -m venv /venv

ENV PATH /venv/bin:$PATH

COPY ./requirements /requirements
RUN . activate && pip install -U pip wheel && pip install --no-cache-dir -r /requirements/base.txt \
    && rm -rf /requirements

WORKDIR /src
COPY . .

CMD ["gunicorn", "escrutinio_social.wsgi"]
