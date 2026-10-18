from setuptools import setup, find_packages

setup(
    name="kitten",
    version="0.1.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "kitten=src.cli:main",
        ],
    },
)
