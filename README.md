naruto-aufs-layers
==================

Wrapper around aufs to make a snapshotting filesystem like thing. Mostly just for fun. 

Usage: naruto [OPTIONS] COMMAND [ARGS]...

  CLI for naruto

Options:
  --naruto-home DIRECTORY  Set default config directory used to store and
                           retrieve layers. Default: /root/.naruto
  -V, --verbosity TEXT     Set verbosity level explicitly (int or CRITICAL,
                           ERROR, WARNING, INFO, DEBUG, NOTSET)
  --help                   Show this message and exit.

Commands:
  add_tags          Add tag to layer
  branch_and_mount  Branch a layer and mount at new dest
  create            Create new NarutoLayer
  delete            Delete a layer
  description       Get set layer description
  find_mounts       Find where layer is mounted
  info              Get info about a layer
  list_home_layers  List layers stored in home directory
  mount             Mount a layer
  remove_tags       Remove tag from layer
  tags              Get set tags
  unmount_all       Unmount all uses of this layer

Output from demo script
=======================
This will demo the functionality of naruto. It will require permissions to mount and will make a number of modifications in /root/.naruto
Naruto is a wrapper around aufs that makes use of its layered filesystem to provide a filesystem that can be easily snapshotted and branched without need to loads of copies

This will have created a new directory in our home
BASH> ls /root/.naruto
my_new_layer
BASH> naruto --verbosity 50 mount /tmp/tmpq0wn9g8p_mount_dir_1 --layer my_new_layer
BASH> echo 'Modification 1' > /tmp/tmpq0wn9g8p_mount_dir_1/file_1.txt
BASH> ls /tmp/tmpq0wn9g8p_mount_dir_1
file_1.txt

Now we can branch this to a new mount point.
BASH> echo 'Modification 2' > /tmp/tmp4wdp6_x4_mount_dir_2/file_1.txt
BASH> ls /tmp/tmp4wdp6_x4_mount_dir_2
file_1.txt
BASH> cat /tmp/tmp4wdp6_x4_mount_dir_2/file_1.txt
Modification 2

BASH> ls /tmp/tmpq0wn9g8p_mount_dir_1
file_1.txt

BASH> cat /tmp/tmpq0wn9g8p_mount_dir_1/file_1.txt
Modification 1

We can display information about a mount point when we're inside it
BASH> cd /tmp/tmpq0wn9g8p_mount_dir_1 ; naruto info
+-- NarutoLayer(id=9831f34df05b4c87af0705506cf8e49a, description=root, tags=(), children=2, descendants=2)
  +-- NarutoLayer(id=158b884793344a68ba094e5718dbc37e, description=None, tags=(), children=0, descendants=0)
  +-- !!!!NarutoLayer(id=de2eeeb01fe946bca89551b0b615ea8b, description=, tags=(), children=0, descendants=0)!!!!

BASH> cd /tmp/tmp4wdp6_x4_mount_dir_2 ; naruto info
+-- NarutoLayer(id=9831f34df05b4c87af0705506cf8e49a, description=root, tags=(), children=2, descendants=2)
  +-- !!!!NarutoLayer(id=158b884793344a68ba094e5718dbc37e, description=None, tags=(), children=0, descendants=0)!!!!
  +-- NarutoLayer(id=de2eeeb01fe946bca89551b0b615ea8b, description=, tags=(), children=0, descendants=0)

Or we can use a query language to look at items
BASH> naruto --verbosity 50 info --layer my_new_layer:root
+-- !!!!NarutoLayer(id=9831f34df05b4c87af0705506cf8e49a, description=root, tags=(), children=2, descendants=2)!!!!
  +-- NarutoLayer(id=158b884793344a68ba094e5718dbc37e, description=None, tags=(), children=0, descendants=0)
  +-- NarutoLayer(id=de2eeeb01fe946bca89551b0b615ea8b, description=, tags=(), children=0, descendants=0)

BASH> naruto --verbosity 50 info --layer my_new_layer:root^
+-- NarutoLayer(id=9831f34df05b4c87af0705506cf8e49a, description=root, tags=(), children=2, descendants=2)
  +-- !!!!NarutoLayer(id=158b884793344a68ba094e5718dbc37e, description=None, tags=(), children=0, descendants=0)!!!!
  +-- NarutoLayer(id=de2eeeb01fe946bca89551b0b615ea8b, description=, tags=(), children=0, descendants=0)

BASH> naruto --verbosity 50 info --layer my_new_layer:root^2
+-- NarutoLayer(id=9831f34df05b4c87af0705506cf8e49a, description=root, tags=(), children=2, descendants=2)
  +-- NarutoLayer(id=158b884793344a68ba094e5718dbc37e, description=None, tags=(), children=0, descendants=0)
  +-- !!!!NarutoLayer(id=de2eeeb01fe946bca89551b0b615ea8b, description=, tags=(), children=0, descendants=0)!!!!

We can also update tags or change descriptions of layers
BASH> cd /tmp/tmpq0wn9g8p_mount_dir_1 ; naruto description new_description
BASH> cd /tmp/tmpq0wn9g8p_mount_dir_1 ; naruto add_tags tag1
BASH> cd /tmp/tmpq0wn9g8p_mount_dir_1 ; naruto info
+-- NarutoLayer(id=9831f34df05b4c87af0705506cf8e49a, description=root, tags=(), children=2, descendants=2)
  +-- NarutoLayer(id=158b884793344a68ba094e5718dbc37e, description=None, tags=(), children=0, descendants=0)
  +-- !!!!NarutoLayer(id=de2eeeb01fe946bca89551b0b615ea8b, description=new_description, tags=('tag1',), children=0, descendants=0)!!!!

Finally we can remove the layer and all its children
BASH> naruto --verbosity 50 delete --no-prompt --layer my_new_layer
WARNING: This layer has 2 direct children and a further 2 descendants.
NarutoLayer(id=9831f34df05b4c87af0705506cf8e49a, description=root, tags=(), children=2, descendants=2) is currently mounted. Must unmount first. Continue?
This will irreversible delete NarutoLayer(id=9831f34df05b4c87af0705506cf8e49a, description=root, tags=(), children=2, descendants=2) and all 2 descendants. Continue?
