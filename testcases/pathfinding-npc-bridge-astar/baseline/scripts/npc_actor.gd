extends CharacterBody3D

@export var movement_speed := 2.6
@export var waypoint_arrival_distance := 0.18
@export var wait_at_target := 0.45

var graph_points: Array[Vector3] = []
var graph_edges: Array[Vector2i] = []
var route_target_ids: Array[int] = []

func configure_pathfinding(points: Array[Vector3], edges: Array[Vector2i], target_ids: Array[int]) -> void:
	graph_points = points.duplicate()
	graph_edges = edges.duplicate()
	route_target_ids = target_ids.duplicate()
	# TODO: Build pathfinding state and start moving between route targets.


func _physics_process(_delta: float) -> void:
	velocity = Vector3.ZERO
	move_and_slide()
