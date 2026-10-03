from runtime.state import state


def runtime_mode(request):
    """Expose technical mode without opening hardware or querying the database."""
    return {"runtime_mode": state.snapshot()}
