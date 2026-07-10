extends Node2D
class_name RespawnSpawner

var respawn_count: int = 0

func on_respawn() -> void:
	respawn_count += 1
