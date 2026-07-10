extends Node3D

const NPC_SCENE := preload("res://scenes/npc_actor.tscn")
const WALK_Y := 0.22

var graph_points: Array[Vector3] = []
var graph_edges: Array[Vector2i] = []
var route_target_ids: Array[int] = []

func _ready() -> void:
	_build_world_geometry()
	_build_path_graph()
	_draw_path_graph_debug()
	_spawn_npc()
	_add_camera_and_light()
	_add_hud()


func _build_world_geometry() -> void:
	_add_box("LeftPlatform", Vector3(-5.0, 0.0, 0.0), Vector3(4.0, 0.35, 4.0), Color(0.18, 0.32, 0.42))
	_add_box("RightPlatform", Vector3(5.0, 0.0, 0.0), Vector3(4.0, 0.35, 4.0), Color(0.18, 0.32, 0.42))
	_add_box("NorthBridge", Vector3(0.0, 0.0, -1.2), Vector3(6.0, 0.3, 0.75), Color(0.42, 0.31, 0.18))
	_add_box("SouthBridge", Vector3(0.0, 0.0, 1.2), Vector3(6.0, 0.3, 0.75), Color(0.42, 0.31, 0.18))
	_add_box("NorthBridgeLeftRail", Vector3(0.0, 0.38, -1.65), Vector3(6.0, 0.18, 0.08), Color(0.22, 0.18, 0.14))
	_add_box("NorthBridgeRightRail", Vector3(0.0, 0.38, -0.75), Vector3(6.0, 0.18, 0.08), Color(0.22, 0.18, 0.14))
	_add_box("SouthBridgeLeftRail", Vector3(0.0, 0.38, 0.75), Vector3(6.0, 0.18, 0.08), Color(0.22, 0.18, 0.14))
	_add_box("SouthBridgeRightRail", Vector3(0.0, 0.38, 1.65), Vector3(6.0, 0.18, 0.08), Color(0.22, 0.18, 0.14))


func _add_box(node_name: String, position: Vector3, size: Vector3, color: Color) -> void:
	var body := StaticBody3D.new()
	body.name = node_name
	body.position = position
	add_child(body)
	var mesh_instance := MeshInstance3D.new()
	var mesh := BoxMesh.new()
	mesh.size = size
	mesh_instance.mesh = mesh
	mesh_instance.material_override = _make_material(color)
	body.add_child(mesh_instance)
	var collision := CollisionShape3D.new()
	var shape := BoxShape3D.new()
	shape.size = size
	collision.shape = shape
	body.add_child(collision)


func _make_material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.roughness = 0.72
	return material


func _make_unshaded_material(color: Color) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	material.no_depth_test = true
	return material


func _build_path_graph() -> void:
	graph_points = [
		Vector3(-5.5, WALK_Y, -1.2),
		Vector3(-5.5, WALK_Y, 1.2),
		Vector3(-3.1, WALK_Y, -1.2),
		Vector3(3.1, WALK_Y, -1.2),
		Vector3(5.5, WALK_Y, -1.2),
		Vector3(5.5, WALK_Y, 1.2),
		Vector3(3.1, WALK_Y, 1.2),
		Vector3(-3.1, WALK_Y, 1.2),
	]
	graph_edges = [
		Vector2i(0, 2), Vector2i(2, 3), Vector2i(3, 4),
		Vector2i(4, 5), Vector2i(5, 6), Vector2i(6, 7), Vector2i(7, 1),
		Vector2i(1, 0), Vector2i(2, 7), Vector2i(3, 6),
	]
	route_target_ids = [4, 5, 1, 0]
	print("[PathGraph] points=%d edges=%d route_targets=%s" % [graph_points.size(), graph_edges.size(), str(route_target_ids)])


func _draw_path_graph_debug() -> void:
	var edge_vertices := PackedVector3Array()
	for edge in graph_edges:
		edge_vertices.append(graph_points[edge.x] + Vector3.UP * 0.08)
		edge_vertices.append(graph_points[edge.y] + Vector3.UP * 0.08)
	_add_debug_mesh("DebugGraphEdges", Mesh.PRIMITIVE_LINES, edge_vertices, Color(0.0, 0.95, 1.0, 1.0))
	for index in range(graph_points.size()):
		var is_route_target := route_target_ids.has(index)
		var color := Color(1.0, 0.15, 0.15, 1.0) if is_route_target else Color(0.25, 0.55, 1.0, 1.0)
		_add_sphere_marker("DebugGraphPoint%d" % index, graph_points[index] + Vector3.UP * 0.24, color, 0.14 if is_route_target else 0.1)


func _add_debug_mesh(node_name: String, primitive: Mesh.PrimitiveType, mesh_vertices: PackedVector3Array, color: Color) -> void:
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = mesh_vertices
	var mesh := ArrayMesh.new()
	if not mesh_vertices.is_empty():
		mesh.add_surface_from_arrays(primitive, arrays)
	var mesh_instance := MeshInstance3D.new()
	mesh_instance.name = node_name
	mesh_instance.mesh = mesh
	mesh_instance.material_override = _make_unshaded_material(color)
	add_child(mesh_instance)


func _add_sphere_marker(node_name: String, position: Vector3, color: Color, radius: float) -> void:
	var marker := MeshInstance3D.new()
	marker.name = node_name
	marker.position = position
	var mesh := SphereMesh.new()
	mesh.radius = radius
	mesh.height = radius * 2.0
	marker.mesh = mesh
	marker.material_override = _make_unshaded_material(color)
	add_child(marker)


func _spawn_npc() -> void:
	var npc := NPC_SCENE.instantiate()
	npc.name = "BridgePathfindingNPC"
	npc.position = graph_points[0]
	add_child(npc)
	npc.configure_pathfinding(graph_points, graph_edges, route_target_ids)


func _add_camera_and_light() -> void:
	var light := DirectionalLight3D.new()
	light.name = "Sun"
	light.rotation_degrees = Vector3(-55.0, -35.0, 0.0)
	light.light_energy = 2.4
	add_child(light)
	var camera := Camera3D.new()
	camera.name = "Camera3D"
	camera.position = Vector3(0.0, 7.0, 9.5)
	camera.current = true
	add_child(camera)
	camera.look_at(Vector3(0.0, 0.0, 0.0), Vector3.UP)


func _add_hud() -> void:
	var hud := CanvasLayer.new()
	hud.name = "HUD"
	add_child(hud)
	var label := Label.new()
	label.text = "AStar3D bridge pathfinding: cyan graph, red route targets, yellow NPC path."
	label.position = Vector2(18.0, 16.0)
	label.add_theme_color_override("font_color", Color(0.92, 0.95, 0.98))
	label.add_theme_font_size_override("font_size", 18)
	hud.add_child(label)