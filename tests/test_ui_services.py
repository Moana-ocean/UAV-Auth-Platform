from app.ui.services import full_environment_status


def test_environment_status_shape():
    env = full_environment_status()
    assert "python" in env
    assert "warnings" in env
    assert "besu_nodes" in env
    assert "topology_note" in env
