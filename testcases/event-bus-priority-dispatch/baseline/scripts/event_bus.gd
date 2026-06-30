extends Node
class_name EventBus

# A priority-ordered event bus.
# Contract:
#   - subscribe(id: String, priority: int): register a subscriber identified by
#     id with the given priority. Higher priority is dispatched FIRST. Ties are
#     dispatched in subscription (insertion) order. Re-subscribing an existing
#     id updates it to the new priority.
#   - unsubscribe(id): remove a subscriber; it must never be dispatched again.
#   - publish(): clear dispatch_log, then append each current subscriber's id to
#     dispatch_log in dispatch order (priority desc, ties by insertion).
#   - publish_removing(remove_id): same as publish(), but remove_id is
#     unsubscribed BEFORE dispatch begins, so it must not appear in the log and
#     every other subscriber must still be dispatched in the correct order
#     (i.e. removal must not corrupt the iteration).
#
# BASELINE: unimplemented.

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
