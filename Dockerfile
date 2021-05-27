FROM python:3.7-slim

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

ENV PYTHONUNBUFFERED 1
ENV PATH /venv/bin:$PATH


WORKDIR /src
COPY . .

RUN . activate && pip install -U pip && pip install -r requirements.txt

CMD ["gunicorn", "escrutinio_social.wsgi"]
