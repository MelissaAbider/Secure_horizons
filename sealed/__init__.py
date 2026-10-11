"""Sealed list (T10): the Safe, the teller-window module and the Merkle list the owners sign.

The agent proposes (sealed.agent_stub, no key). The platform encodes, finds the proof and submits with the operator
key (sealed.teller). The module runs only operations sealed in the root that the Safe owners signed (sealed.seal).
"""
