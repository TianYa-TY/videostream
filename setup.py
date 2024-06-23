# -*- coding: utf-8 -*-

from pkg_resources import parse_requirements
from setuptools import find_packages, setup


if __name__ == '__main__':
    with open("requirements.txt", encoding="utf-8") as f:
        install_requires = [str(requirement) for requirement in parse_requirements(f.read())]

    setup(
        name="videostream",
        version="1.0.0",
        author="ty",
        description="A pull and push video stream tool",
        license="MIT",

        packages=find_packages(),
        install_requires=install_requires,
        python_requires=">=3.9, <4",
        classifiers=[
            "Programming Language :: Python :: 3.9",
            "Programming Language :: Python :: 3.10",
            "Programming Language :: Python :: 3.11",
            "Programming Language :: Python :: 3.12",
        ]
    )

