from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="DPM",
    version="0.1.0",
    author="ZenSharp",
    author_email="andtechstudios@gmail.com",
    description="A package manager for your dotfiles.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/zensharp/dpm",
    packages=setuptools.find_packages(),
    entry_points = {
        'console_scripts': ['dpm=src.dpm:main'],
    }
)