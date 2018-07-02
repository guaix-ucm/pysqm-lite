
from setuptools import setup

setup(
    name='pysqml',
    version='0.1',
    author='Sergio Pascual',
    author_email='sergiopr@fis.ucm.es',
    url='http://guaix.fis.ucm.es/hg/pysqml/',
    license='GPLv3',
    description='Minimal SQM reading software',
    packages=['pysqml'],
    install_requires=['pyserial', 'paho-mqtt'],
    entry_points={
        'console_scripts': [
            'pysqm_lite = pysqml.cli:main'
        ]
    },
    zip_safe=False,
    classifiers=[
        "Programming Language :: C",
        "Programming Language :: Cython",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: Implementation :: CPython",
        'Development Status :: 3 - Alpha',
        "Environment :: Other Environment",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: GNU General Public License (GPL)",
        "Operating System :: OS Independent",
        "Topic :: Scientific/Engineering :: Astronomy",
    ],
    long_description=open('README.txt').read()
)
