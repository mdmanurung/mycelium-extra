#!/bin/sh
# Kept for hook registrations and old callers: the launcher now lives in mxpy (see there).
case $0 in */*) dir=${0%/*} ;; *) dir=. ;; esac
exec /bin/sh "$dir/mxpy" "$@"
