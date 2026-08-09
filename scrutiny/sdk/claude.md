This is the Scrutiny Software Development Kit meant to interact with a Scrutiny server from a Python Script.
To understand this module, reads the documentation at ``docs/sdk`` and also the docstrings. Everything is there.

The ``ScrutinyClient`` runs a worker thread (function with prefix ``wt_`` belongs to that thread). This thread communicates with the server.
Other methods expected to be called by the user from its own threads. These methods must be thread safe.
A user is allowed to invoke a ``Client`` public method from  multiple threads and everything is expected to behave properly.
