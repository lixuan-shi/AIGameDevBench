extends Node2D

func spawn_goblin() -> Node:
	var goblin_path := "res://entities/goblin.tscn"
	var packed: PackedScene = load(goblin_path)
	var instance := packed.instantiate()
	add_child(instance)
	return instance
