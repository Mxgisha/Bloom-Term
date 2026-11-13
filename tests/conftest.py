import os

# Tests must never touch the network. Set before anything imports app.main.
os.environ["BLOOMTERM_PROVIDER"] = "mock"
