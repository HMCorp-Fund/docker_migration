from setuptools import setup, find_packages

setup(
    name="docker-migration",
    version="0.1.0",
    author="Anton Pavlenko",
    author_email="your.email@example.com",
    description="A tool for migrating Docker applications between servers",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/HMCorp-Fund/docker-migration",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        "docker",
        "requests",
        "paramiko",
        "pyyaml>=6.0",
        "zipfile36",
    ],
    entry_points={
        'console_scripts': [
            'docker-migration=docker_migration.main:main',
        ],
    },
)