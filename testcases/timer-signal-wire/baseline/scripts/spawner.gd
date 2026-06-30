extends Node2D
class_name RespawnSpawner

# The spawner wants a RespawnTimer child whose timeout drives on_respawn().
# on_respawn() is already implemented; the scene wiring is what's missing.

var respawn_count: int = 0

func on_respawn() -> void:
	respawn_count += 1
