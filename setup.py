from setuptools import setup, find_packages

setup(
    name="poolgpu",
    version="0.1.0",
    description="GPU 资源池调度系统",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "flask>=2.0",
        "flask-socketio>=5.0",
        "paramiko>=2.7",
        "psutil>=5.8",
        "click>=8.0",
        "pyyaml>=5.4",
    ],
    entry_points={
        "console_scripts": [
            "poolgpu=cli.main:cli",
        ],
    },
)
