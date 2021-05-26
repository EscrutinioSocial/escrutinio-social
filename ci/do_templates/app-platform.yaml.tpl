databases:
  - cluster_name: ${DB_CLUSTER_NAME}
    db_name: escrutinio-social
    db_user: escrutinio-social
    engine: PG
    name: db
    num_nodes: 1
    production: true
    size: db-s-dev-database
    version: "12"
domains:
- domain: ${APP_DOMAIN}
  type: PRIMARY
envs:
  - key: DB_NAME
    scope: RUN_AND_BUILD_TIME
    value: ${db.DATABASE}
  - key: DB_USER
    scope: RUN_AND_BUILD_TIME
    value: ${db.USERNAME}
  - key: DB_PASS
    scope: RUN_AND_BUILD_TIME
    value: ${db.PASSWORD}
  - key: DB_HOST
    scope: RUN_AND_BUILD_TIME
    value: ${db.HOSTNAME}
  - key: DB_PORT
    scope: RUN_AND_BUILD_TIME
    value: ${db.PORT}
  - key: AWS_ACCESS_KEY_ID
    scope: RUN_AND_BUILD_TIME
    value: ${AWS_ACCESS_KEY_ID}
  - key: AWS_SECRET_ACCESS_KEY
    scope: RUN_AND_BUILD_TIME
    value: ${AWS_SECRET_ACCESS_KEY}
  - key: AWS_STORAGE_BUCKET_NAME
    scope: RUN_AND_BUILD_TIME
    value: ${AWS_STORAGE_BUCKET_NAME}
  - key: AWS_S3_ENDPOINT_URL
    scope: RUN_AND_BUILD_TIME
    value: ${AWS_S3_ENDPOINT_URL}
jobs:
  - dockerfile_path: Dockerfile
    envs:
      - key: DATABASE_URL
        scope: RUN_TIME
        value: ${db.DATABASE_URL}
    github:
      branch: one-process-one-container
      deploy_on_push: true
      repo: EscrutinioSocial/escrutinio-social-peru
    instance_count: 1
    instance_size_slug: basic-xxs
    kind: PRE_DEPLOY
    name: migrate
    run_command: python manage.py migrate
    source_dir: /
  - dockerfile_path: Dockerfile
    envs:
      - key: DATABASE_URL
        scope: RUN_TIME
        value: ${db.DATABASE_URL}
    github:
      branch: one-process-one-container
      deploy_on_push: true
      repo: EscrutinioSocial/escrutinio-social-peru
    instance_count: 1
    instance_size_slug: basic-xxs
    kind: PRE_DEPLOY
    name: collectstatic
    run_command: python manage.py collectstatic --no-input
    source_dir: /
name: escrutinio-social-peru
region: ${APP_REGION}
services:
  - dockerfile_path: Dockerfile
    envs:
      - key: DATABASE_URL
        scope: RUN_TIME
        value: ${db.DATABASE_URL}
      - key: GUNICORN_WORKERS
        scope: RUN_AND_BUILD_TIME
        value: "${GUNICORN_WORKERS}"
      - key: DJANGO_SECRET_KEY
        scope: RUN_AND_BUILD_TIME
        value: ${DJANGO_SECRET_KEY}
      - key: DJANGO_ALLOWED_HOSTS
        scope: RUN_AND_BUILD_TIME
        value: ${APP_DOMAIN}
    github:
      branch: one-process-one-container
      deploy_on_push: true
      repo: EscrutinioSocial/escrutinio-social-peru
    http_port: 8000
    instance_count: 1
    instance_size_slug: basic-xs
    name: app
    routes:
      - path: /
    run_command: gunicorn --worker-tmp-dir /dev/shm escrutinio_social.wsgi
    source_dir: /
workers:
  - dockerfile_path: Dockerfile
    envs:
      - key: DATABASE_URL
        scope: RUN_TIME
        value: ${db.DATABASE_URL}
    github:
      branch: one-process-one-container
      deploy_on_push: true
      repo: EscrutinioSocial/escrutinio-social-peru
    instance_count: 1
    instance_size_slug: basic-xxs
    name: scheduler
    run_command: python manage.py scheduler
    source_dir: /
