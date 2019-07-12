#!/usr/bin/env bash

set -e

# We first login to the registry
$(aws ecr get-login --no-include-email --region ${REGION})

# build image and push image
docker build -t "${CONTAINER_IMAGE}" .
docker push "${CONTAINER_IMAGE}"

#echo "${CONTAINER_IMAGE}" > container_image
