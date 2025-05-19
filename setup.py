from setuptools import setup, find_packages

setup(
    name="docker-migration",
    version="0.2.0",  # Increment version number
    author="Anton Pavlenko",
    author_email="apavlenko@hmcorp.fund",
    description="A tool for migrating Docker applications between servers",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/HMCorp-Fund/docker_migration",
    packages=find_packages(),
    python_requires=">=3.6",
    install_requires=[
        "docker",
        "requests",
        "paramiko",
        "pyyaml",
        "zipfile36",
        "humanize",
    ],
    entry_points={
        'console_scripts': [
            'docker-migration=docker_migration.main:main',
        ],
    },
)