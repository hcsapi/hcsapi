from setuptools import setup, find_packages
from os import path

this_directory = path.abspath(path.dirname(__file__))

with open(path.join(this_directory, "README.md"), encoding="utf-8") as f:
    long_description = f.read()

with open(path.join(this_directory, "requirements.txt")) as f:
    requirements = f.readlines()

setup(
    name='hcsapi',

    version='1.15.5',

    description='자가진단 자동화 비공식 Api (Automation tool for https://hcs.eduro.go.kr/)',
    license='GPL-V3',
    author='scottjsh & excutetype',

    
    url='https://github.com/hcsapi/hcsapi',

    download_url='https://github.com/hcsapi/hcsapi',

    long_description=long_description,
    long_description_content_type='text/markdown',

    install_requires=requirements,

    packages=find_packages(),

    keywords=['korea', 'covid', 'auto', 'hcs'],

    python_requires='>=3.4',


    classifiers=[
        'Programming Language :: Python :: 3.8',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        #'Development Status :: 3 - Alpha',
        'Development Status :: 5 - Production/Stable',
    ],
)
