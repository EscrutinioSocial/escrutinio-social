#!/usr/bin/env bash
set -e

export AWS_DEFAULT_REGION=${REGION}
PATHDIR='./ci/ecs_templates'

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
elif [[ "${CI_COMMIT_REF_NAME}" = "develop" ]] ; then
    export ENVIRONMENT="DEV"
    export ECS_CLUSTER="Convencer-Test"

    echo
    echo "Deploying DEVELOP Branch to DEV Cluster"
    echo

else
    echo
    echo "Only deploy master or develop branch"
    echo
    export ENVIRONMENT="PROD"
    export ECS_CLUSTER="ECS-PROD"
    #exit 2
fi

# Generating final manifest
echo "Generating final Service Manifest"
envsubst < ${PATHDIR}/escrutinio-paralelo-svc.json.template > ${PATHDIR}/escrutinio-paralelo-svc.json

# Showing final manifest
cat ${PATHDIR}/escrutinio-paralelo-svc.json

# Deploying 
echo "Deploying service"
aws ecs update-service --cli-input-json file://${PATHDIR}/escrutinio-paralelo-svc.json --force-new-deployment

# Output Info
echo "Check deployment at: http://ecs-lb-2004188673.sa-east-1.elb.amazonaws.com"
