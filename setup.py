from setuptools import find_packages, setup


# get package version
with open('VERSION') as version_file:
    version = version_file.read().strip()

# assemble requirements
with open('requirements_pkg.txt') as f:
    requirements_pkg = f.read().splitlines()

with open('requirements_dev.txt') as f:
    requirements_dev = f.read().splitlines()

# load the README file and use it as the long_description for PyPI
with open('README.md', 'r') as f:
    readme = f.read()

setup(
    name='bodywork',
    description='Machine learning and statistical model deployment frameowrk.',
    long_description=readme,
    long_description_content_type='text/markdown',
    version=version,
    license='Apache 2.0',
    author='Alex Ioannides',
    url='https://github.com/bodywork-ml/bodywork',
    package_dir={'': 'src'},
    packages=find_packages(where='src'),
    include_package_data=True,
    python_requires=">=3.7.*",
    install_requires=requirements_pkg,
    extras_require={
        'dev': requirements_dev,
    },
    zip_safe=True,
    entry_points={
        'console_scripts': [
            'bodywork=bodywork.cli.cli:cli'
        ]
    }
)
