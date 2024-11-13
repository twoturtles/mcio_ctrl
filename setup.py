from setuptools import setup, find_packages

setup(
    name="mcio_remote",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        'cbor2>=5.6.5',
        'glfw>=2.7.0'
    ],
    author="TwoTurtles",
    description="Python interface to connect to the MCio Minecraft mod",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/twoturtles/mcio_remote",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
)