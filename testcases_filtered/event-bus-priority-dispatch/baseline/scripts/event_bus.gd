extends Node
class_name EventBus

var dispatch_log: Array = []

var _subs: Array = []   # array of {"id":String, "priority":int}

func subscribe(id: String, priority: int) -> void:
	# TODO
	pass

func unsubscribe(id: String) -> void:
	# TODO
	pass

func publish() -> void:
	# TODO
	pass

func publish_removing(remove_id: String) -> void:
	# TODO
	pass
