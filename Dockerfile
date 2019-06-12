FROM python:3.7
ENV PYTHONUNBUFFERED 1
RUN apt-get update && apt-get install -y \
    binutils \
    git \
    libproj-dev \
    gdal-bin
RUN mkdir /src
WORKDIR /src
ADD requirements.txt /src/
RUN pip install -r requirements.txt
CMD python manage.py migrate
ADD . /src/