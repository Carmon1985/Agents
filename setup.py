from setuptools import setup, find_packages

setup(
    name="resource-monitoring-agents",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "pydantic>=2.0.0",
        "pytest>=7.0.0",
        "pytest-asyncio>=0.20.0",
        "streamlit>=1.0.0",
        "autogen>=1.0.0",
        "python-dotenv>=1.0.0",
        "pandas>=2.0.0"
    ],
    python_requires=">=3.8",
) 