"""Tamper-evident audit records."""

from aiguard.audit.log import GENESIS_HASH, event_to_dict, record_event, verify_chain

__all__ = ["GENESIS_HASH", "event_to_dict", "record_event", "verify_chain"]
