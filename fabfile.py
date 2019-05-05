from fabric.api import run, env, cd, prefix
from fabric.decorators import roles
from fabric.contrib.files import append
from escrutinio_social.local_settings import (HOSTS, HOST_USER, VENV,
                                                PROJECT_PATH, PROJECT_USER,
                                                ROLE_DEFS)

env.hosts = HOSTS
env.user = HOST_USER
env.roledefs.update(ROLE_DEFS)

@roles(PROJECT_USER)
def manage(command):
    with prefix(f"source {VENV}bin/activate"), cd(PROJECT_PATH):
        run(f"{VENV}bin/python manage.py {command}")


def shell_plus():
    manage('shell_plus')


def dbbackup():
    manage('dbbackup -z')


def dbrestore():
    manage('dbrestore -z')


def clear_cache():
    manage('clear_cache')


def append_to_local_settings(path):
    with open(path) as ls:
        content = ls.read()
    with prefix(f"source  {VENV}bin/activate"), cd(PROJECT_PATH):
        append('./escrutinio_social/local_settings.py', f'\n{content}')


def rmpyc():
    with cd(PROJECT_PATH):
        run("find . -type d -name \"__pycache__\" -exec rm -rf {} \;")


def loaddata(fixture):
    manage("loaddata fixtures/{}".format(fixture))


def importar_actas():
    manage("importar_actas --include-seen --only-images")


def deploy():
    with cd(PROJECT_PATH):
        run("git pull")
    run("sudo supervisorctl restart escrutinio")


def full_deploy():
    with cd(PROJECT_PATH):
        run("git pull")
        run("git checkout master")
        run(f"{VENV}bin/pip install -r requirements.txt")
    manage("migrate")
    # NO CREO QUE LO NECESITEMOS manage("loaddata fixtures/neuquen.json")
    manage("collectstatic --noinput")
    run("sudo supervisorctl restart escrutinio")