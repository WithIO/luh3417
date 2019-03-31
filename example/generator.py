import re
from os import getenv
from os.path import basename, join
from typing import Text

from luh3417.luhfs import parse_location
from luh3417.transfer import UnknownEnvironment
from luh3417.utils import random_password

DEV_SERVER = "root@my-dev-server.com"
PROD_SERVER = "root@my-prod-server.com"

PROD_DOMAIN = "www.my-website.com"
DEV_DOMAIN = "my-org.com"

PROJECT = "foo"
WILDCARD_NAME = 'my-org'

THEME_NAME = "jupiter-child"
THEME_REPO = "git@gitlab.com:my-org/jupiter_child.git"

FEATURE_RE = r"^feature/[a-z]([0-9]+)(?:_[a-z0-9]+)+$"


def get_source(environment: Text):
    """
    MANDATORY

    Given the environment name, generates the source location where it should
    be found.

    We have several environments allowed:

    - prod -- The production website
    - staging -- The staging website, which is basically a buffer before
      pushing to production
    - develop -- The development website
    - feature/x42_name -- A feature branch to be deployed for testing before
      merging. The `x` can be any letter, the `42` is the number of the ticket
      and the `_name` is just a friendly name for the feature. It corresponds
      exactly to the name of the Git branch.
    """

    m = re.match(FEATURE_RE, environment)

    if environment == "prod":
        return f"{PROD_SERVER}:/var/apps/{PROJECT}/prod"
    elif environment == "staging":
        return f"{DEV_SERVER}:/var/apps/{PROJECT}/staging"
    elif environment == "develop":
        return f"{DEV_SERVER}:/var/apps/{PROJECT}/dev"
    elif environment == "local":
        home = getenv("HOME")

        if not home:
            raise UnknownEnvironment(
                "Could not detect home location from HOME environment variable"
            )

        return join(home, "dev", PROJECT, "wp")
    elif m:
        return f"{DEV_SERVER}:/var/apps/{PROJECT}/feature_{m.group(1)}"

    raise UnknownEnvironment('Expecting "staging", "develop" or "feature/..."')


def allow_transfer(origin: Text, target: Text):
    """
    MANDATORY

    The core is the develop version, onto which all things are tested.

    Then there is the staging and prod versions which are basically the same
    thing. Staging is just a buffer for prod onto which you can make changes
    before actually pushing to production. You can also pull back production
    onto staging if you made live updates.

    Develop aims to be overwritten by staging regularly.

    Feature branches are based on develop.

    And finally local deployments can be clones of any other environment.

    All of that is very inspired by git-flow albeit not perfectly identical.
    """

    if origin == "prod" and target == "staging":
        return True
    elif origin == "staging" and target == "prod":
        return True
    elif origin == "staging" and target == "develop":
        return True
    elif origin == "develop" and target.startswith("feature/"):
        return True
    elif target == "local":
        return True
    else:
        return False


def get_backup_dir(environment: Text):
    """
    MANDATORY

    Generates the path to backups given an environment. Everything is backed
    on the dev server, except the local deployments which are backed on the
    local machine.
    """

    if environment == "local":
        return f'{getenv("HOME")}/backups/{PROJECT}'
    else:
        return f"{DEV_SERVER}:/var/backups/wp/{PROJECT}"


def get_patch(origin: Text, target: Text):
    """
    MANDATORY

    Generates the patch which will be used for restoring. Please note that the
    wp_config part of the patch is generated externally and managed by
    transfer itself.

    - owner -- In local, current user owns the file, on the servers it's
      www-data
    - git -- All the changes we make go to a child theme which is managed by
      git. The git repo is created on all environments except production (this
      way backups can easily be deployed)
    - php_define -- A dictionary of wp-config.php values to change/set. We
      set the Sentry environment to the target name and also disable the
      WP_CACHE if deployed in local.
    - mysql_root -- On all environments except production, automatically
      manage the DB and DB user.
    - replace_in_dump -- Replaces in the dump the old URL with the new URL
    """

    if target == "local":
        sentry_env = f'{basename(getenv("HOME"))}_local'
    else:
        sentry_env = target

    if target == "prod":
        mysql_root = None
    elif target == "local":
        mysql_root = {"method": "socket", "options": {"sudo_user": "root"}}
    else:
        mysql_root = {"method": "socket"}

    outer_files = [
        {
            "name": f"/etc/apache2/sites-available/{get_domain(target)}.conf",
            "content": make_virtual_host(target),
        }
    ]

    if target != "prod":
        outer_files.append({
            "name": "robots.txt",
            "content": "User-agent: *\nDisallow: /\n"
        })

    return {
        "owner": None if target == "local" else "www-data:",
        "git": [
            {
                "location": f"wp-content/themes/{THEME_NAME}",
                "repo": THEME_REPO,
                "version": get_git_version(target),
            }
        ] if target != 'prod' else [],
        "php_define": {"WP_SENTRY_ENV": sentry_env, "WP_CACHE": target != "local"},
        "mysql_root": mysql_root,
        "replace_in_dump": [
            {"search": get_base_url(origin), "replace": get_base_url(target)}
        ],
        "outer_files": outer_files,
    }


def get_wp_config(environment: Text):
    """
    MANDATORY

    Generates a wp_config (db user, name, etc) for the environment. This is
    called by transfer when there is no pre-existing wp_config in that
    environment.
    """

    m = re.match(FEATURE_RE, environment)
    prefix = PROJECT

    if environment == "prod":
        db = f"{prefix}_prod"
    elif environment == "staging":
        db = f"{prefix}_staging"
    elif environment == "develop":
        db = f"{prefix}_dev"
    elif environment == "local":
        user = basename(getenv("HOME"))
        db = f"{prefix}_{user}"
    elif m:
        db = f"{prefix}_feature_{m.group(1)}"
    else:
        db = prefix

    return {
        "db_host": "localhost",
        "db_user": db,
        "db_name": db,
        "db_password": random_password(),
    }


def get_git_version(environment: Text):
    """
    Utility method to determine the git branch depending on the environment.
    """

    if environment == "prod":
        return "master"
    elif environment == "staging":
        return "master"
    elif environment == "local":
        return "develop"
    else:
        return environment


def get_base_url(environment: Text) -> Text:
    """
    Utility method to determine the domain name to use depending on the
    environment.
    """

    return f"https://{get_domain(environment)}"


def get_domain(environment: Text) -> Text:
    """
    Computes the domain name provided the environment
    """

    m = re.match(FEATURE_RE, environment)

    if environment == "prod":
        return PROD_DOMAIN
    elif environment == "staging":
        return f"{PROJECT}-wp.{DEV_DOMAIN}"
    elif environment == "develop":
        return f"{PROJECT}-wp-dev.{DEV_DOMAIN}"
    elif environment == "local":
        user = basename(getenv("HOME"))
        return f"{user}-{PROJECT}.{DEV_DOMAIN}"
    elif m:
        return f"{PROJECT}-wp-feature-{m.group(1)}.{DEV_DOMAIN}"


def get_install_dir(environment: Text) -> Text:
    """
    Returns the installation path of the environment on the server
    """

    return parse_location(get_source(environment)).path


def make_virtual_host(environment: Text) -> Text:
    """
    Generates a virtual environment file for the given environment
    """

    return f"""
        <VirtualHost *:443>
            ServerName {get_domain(environment)}
            DocumentRoot {get_install_dir(environment)}

            ErrorLog ${{APACHE_LOG_DIR}}/{get_domain(environment)}.{DEV_DOMAIN}_error.log
            CustomLog ${{APACHE_LOG_DIR}}/{get_domain(environment)}.{DEV_DOMAIN}_access.log combined

            SSLEngine on
            SSLCertificateFile /etc/apache2/ssl/{WILDCARD_NAME}.crt
            SSLCertificateKeyFile /etc/apache2/ssl/{WILDCARD_NAME}.key
            SSLCertificateChainFile /etc/apache2/ssl/{WILDCARD_NAME}.chain
        
            SSLCipherSuite EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH
            SSLProtocol All -SSLv2 -SSLv3 -TLSv1 -TLSv1.1
            SSLHonorCipherOrder On

            <Directory {get_install_dir(environment)}>
                Require all granted
                AllowOverride all
            </Directory>
        </VirtualHost>

        <VirtualHost *:80>
            ServerName {get_domain(environment)}
            DocumentRoot {get_install_dir(environment)}
            Redirect permanent / https://{get_domain(environment)}/
        </VirtualHost>
"""

