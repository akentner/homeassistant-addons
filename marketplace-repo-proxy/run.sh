#!/bin/sh
# s6 oneshot "init": directories, gitconfig and the access symlink tree (reads /data/options.json directly)
cd /opt/marketplace-repo-proxy || exit 1
exec env PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 python3 -m app.init
