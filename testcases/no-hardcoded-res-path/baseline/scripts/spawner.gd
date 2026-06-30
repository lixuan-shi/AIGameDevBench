extends Node2D

# Spawns goblins. The scene to spawn is currently selected by a hardcoded
# res:// path string at the call site, which couples this script to a literal
# asset location.

func spawn_goblin() -> Node:
	var goblin_path := "res://entities/goblin.tscn"
	var packed: PackedScene = load(goblin_path)
	var instance := packed.instantiate()
	add_child(instance)
	return instance
