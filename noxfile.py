import nox


@nox.session(python=False)
def lint(session):
    """perform linter processes"""
    session.run("pdm", "run", "isort", "src", "tests")
    session.run("pdm", "run", "black", "src", "tests")
    session.run("pdm", "run", "flake8", "src", "tests")


@nox.session(python=False)
def tests(session):
    """conduct testing"""
    session.run("pdm", "run", "pytest")
