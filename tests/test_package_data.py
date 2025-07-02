import importlib.resources as resources


def test_py_typed_in_package():
    # Ensure py.typed marker is included for PEP 561 compliance
    assert resources.files("typecheck").joinpath("py.typed").is_file(), "py.typed missing from package"
