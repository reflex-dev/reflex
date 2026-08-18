The workflow compiler now rejects handler bodies that silently break durability: calling another durable handler inline, or returning a plain value instead of a transition.
