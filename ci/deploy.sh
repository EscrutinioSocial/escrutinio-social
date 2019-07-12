#!/usr/bin/env bash
set -e

export AWS_DEFAULT_REGION=${REGION}
PATHDIR='./ci/ecs_templates'

pwd

# MASTER
################################################
if [[ "${CI_COMMIT_REF_NAME}" = "master" ]] ; then
    export ENVIRONMENT="PROD"
    export ECS_CLUSTER="ECS-PROD"
    echo
    echo "Deploying MASTER Branch to PROD"
    echo

# DEVELOPMENT
################################################
elif [[ "${CI_COMMIT_REF_NAME}" = "setup-ci" ]] ; then
    export ENVIRONMENT="DEV"
    export ECS_CLUSTER="Convencer-Test"

    echo
    echo "Deploying DEVELOP Branch to DEV Cluster"
    echo

else
    echo
    echo "Only deploy master or develop branch"
    echo
    exit 2
fi

# Generating final manifest
echo "Generating final Service Manifest"
envsubst < ${PATHDIR}/escrutinio-paralelo-svc.json.template > ${PATHDIR}/escrutinio-paralelo-svc.json

# Showing final manifest
cat ${PATHDIR}/escrutinio-paralelo-svc.json

# Deploying 
echo "Deploying service"
aws ecs update-service --cli-input-json file://${PATHDIR}/escrutinio-paralelo-svc.json --force-new-deployment
