LUH3417
=======

This is a tool to help you implement a WordPress development workflow. It has 3
main features:

- **Snapshot** &mdash; Take snapshots of a running WordPress instance
- **Restore** &mdash; Restore those snapshots in-place or to a different
  location
- **Transfer** &mdash; Transfer one instance over another using automated
  backup, validation and configuration rules
  
Everything can happen seamlessly in *local* or *through SSH*, allowing you to
work easily on remote servers from your local machine and to transfer instances
from one server to another.
  
Thanks to this, putting your code to production is as simple as:

```bash
python -m luh3417.transfer -g my_project.py local production 
```

While the `snapshot` and `restore` operations can be used individually, it is
not recommended to use them as the main tools. Indeed, `restore` can easily
override an instance without any previous backup. For this reason, it is better
to use `transfer` whenever possible. It will ensure your safety within the
workflow that you defined.

## Usage

LUH3417 is made to use with Python's `-m` option. This way, if you want to
invoke the `snapshot` feature, the base command will be 
`python -m luh3417.snapshot`.

All the locations can be in two formats:

- `SSH` &mdash; `user@server:/location/on/server`
- `Local` &mdash; `/location/on/current/machine`

This allows you to transfer data between remote servers and local machine quite
seamlessly.

> **NOTE** &mdash; You need to use an SSH agent in order for all the features
> to work. No password prompt will show up. Usually it's as simple as to type
> `ssh-add` in your terminal once during your session.

### `snapshot`

Creates a snapshot of a running WordPress instance. A snapshot is an archive
containing:

- All PHP/theme/media/etc files
- A DB dump
- Meta information about how the snapshot was taken

Usage syntax:

```
python -m luh3417.snapshot [-h] [-n SNAPSHOT_BASE_NAME] [-t FILE_NAME_TEMPLATE] source backup_dir
```

Example:

```
python -m luh3417.snapshot root@prod-server.com:/var/www/html root@backup-server.com:/var/backups/wp
```

Additional options:

- `-n`/`--snapshot-base-name` &mdash; Base name for your snapshot file. See
  the `--file-name-template` option to see how this name is used. The default
  name is the database's name.
- `-t`/`--file-name-template` &mdash; This template will be used to generate
  the snapshot file name. By default it is `{base}_{time}.tar.gz` but you can
  put whatever you want. `{base}` and `{time}` will be replaced respectively
  by the base name (see `--snapshot-base-name`) and the ISO 8601 UTC date.
  Independently of the name, the file will be placed in the `backup_dir`.
  
### `restore`

Restores a snapshot either in-place to its original location using the embedded
meta-data or to another location using a patch on the meta-data.

In addition to just restoring the files and database, the patch can trigger
changes in `wp-settings.php`, replace values in the database and much more.

**`restore` will essentially override an instance with the content of a
backup, so make sure to use it wisely in order not to loose data. Also, see
`transfer`**.

Usage:

```
python -m luh3417.restore [-p PATCH] [-a ALLOW_IN_PLACE] snapshot
```

Options:

- `-p`/`--patch` &mdash; Location to the patch file (see below)
- `-a`/`--allow-in-place` &mdash; Allows restoring the backup onto its original
  location. This flag is required because otherwise it would be way too easy
  to override
  
#### Restore in-place

If you want to restore a backup to its original location, you just need to
know the file's location and pass the `-a` flag.

```
python -m luh3417.restore -a root@backup-server.com:/path/to/snapshot.tar.gz
```

> **NOTE** &mdash; If the snapshot was made locally, it will always be restored 
> locally because there is no way for LUH3417 to know the originating server so
> it assumes that the snapshot file was not transferred to another machine.

#### Restore to another location

In order to restore to another location, you need to use a patch file

```
python -m luh3417.restore -p patch.json root@backup-server.com:/path/to/snapshot.tar.gz
```

Here is an example of patch file:

```json
{
    "args": {
        "source": "root@new-server.com:/var/www/html"
    },
    "owner": "www-data:"
}
```

See below for detailed documentation of patch content

##### `args.source`

Set this one to define where to restore the archive.

```json
{
    "args": {
        "source": "root@new-server.com:/var/www/html"
    }
}
```

#### `wp_config`

Database configuration from the WordPress

```json
{
    "wp_config": {
        "db_host": "localhost",
        "db_name": "xxx",
        "db_user": "xxx",
        "db_password": "xxx"
    }
}
```

> **NOTE** &mdash; You need to make sure you match those values in `php_define`
> unless you're using `transfer` which sets them automatically

##### `owner`

This changes the owner of the files to another one. This only works if:

- When restoring locally, you run as `root`
- When restoring remotely, you login in as `root`

```json
{
    "owner": "www-data:"
}
```

##### `git`

Replaces some directories with a Git repository at a given version

```json
{
    "git": [
        {
            "location": "wp-content/themes/jupiter-child",
            "repo": "git@gitlab.com:your_company/jupiter_child.git",
            "version": "master"
        }
    ]
}
```

> **NOTE** &mdash; `.git` directories are excluded from snapshots, so unless
> you specify this option there will be no git-enabled directories in the
> restored files. On the other hand, git repositories will be created at
> specified version, so it might not make sense to specify this option when
> restoring a backup in-place.

##### `setup_queries`

A list of SQL queries to be run after the DB was restored

```json
{
    "setup_queries": [
        "delete from wp_options where option_name = 'gtm4wp-options';"
    ]
}
```

##### `php_define`

Values to be changed or added in `wp-config.php`. Any JSON-serializable value
can be used.

```json
{
    "php_define": {
        "WP_CACHE": false,
        "WP_SENTRY_ENV": "new-env"
    }
}
```

##### `replace_in_dump`

A list of strings with their replacement to be changed in the dump before
restoring it. This is mainly used to change the domain name of the instance.
As WordPress serializes its settings, a simple replace is not possible. This
will use a holistic heuristic which will try to keep PHP-serialized values
correct even if quoted in a MySQL string.

> **NOTE** &mdash; PHP-serialized values are prefixed by their length, this is
> why a simple replace cannot be effective: if the length changes then the
> whole value gets corrupted.

```json
{
    "replace_in_dump": [
        {
            "search": "https://old-domain.com",
            "replace": "https://new-domain.com"
        }
    ]
}
```

##### `mysql_root`

In order to create the database and set the user password, the script needs
a root access to MySQL. Today, the only supported method is `socket`, because
it is password-less. However it only works when the server is local and 
properly configured (it's the default behavior in Debian-based distros).

```json
{
    "mysql_root": {
        "method": "socket",
        "options": {
            "sudo_user": "root",
            "mysql_user": "root"
        }
    }
}
```

About the options:

- `sudo_user` &mdash; don't set it if you don't need to sudo to use the socket,
  set it to `root` or whichever user is right otherwise.
- `mysql_user` &mdash; name of the MySQL user to use

### `transfer`

The main goal of this package is to allow the setup of a custom workflow that
allows easy copy of WordPress instances from an environment from the other.

The basic idea is the following:

- You can specify an origin and target environment names
- There is a *settings generator* Python file which will generate all the
  settings and patches appropriate for this transfer.
  
It's **your responsibility** to write an settings generator, however there is
an a documented example attached in this repository.

Usage:

```
python -m luh3417.transfer [-h] -g SETTINGS_GENERATOR origin target
```

Example:

```
python -m luh3417.transfer -g example/generator.py develop local
```

To see the content of the generator file, please refer to the
[example/generator.py](example/generator.py) file and especially the
`allow_transfer()` method's documentation which will explain the spirit of
the file.

## FAQ

> Why the name `LUH3417`?

It's a character from THX1138. The author is not particularly fan of this
movie, however it expresses quite well the feeling of working with WordPress
and especially setting up a professional workflow.

> Why using Python to code it?

It felt to the author that this language was more appropriate for this task 
than PHP.

> Do I need to write Python to use the transfer feature?

Yes, fortunately it's pretty easy. The author started with
[Dive Into Python](https://www.diveinto.org/python3/).

> Why can't the transfer feature have a configuration file instead?

A configuration file would mean imposing the skeleton of the author's workflow
onto all users. If such a workflow is suitable for your needs, example code
and tutorial are provided so just have to adapt the code for yourself.

## License

This project is distributed under the terms of the [WTFPL](./COPYING). It comes
void of warranties and if you break things it's on you.