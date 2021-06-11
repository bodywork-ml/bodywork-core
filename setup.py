# bodywork - MLOps on Kubernetes.
# Copyright (C) 2020-2021  Bodywork Machine Learning Ltd.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from setuptools import find_packages, setup
from urllib import request, parse, error


# get package version
with open("VERSION") as version_file:
    version = version_file.read().strip()

# assemble requirements
with open("requirements_pkg.txt") as f:
    requirements_pkg = f.read().splitlines()

with open("requirements_dev.txt") as f:
    requirements_dev = f.read().splitlines()

# load the README file and use it as the long_description for PyPI
with open("README.md", "r") as f:
    readme = f.read()

setup(
    name="bodywork",
    description="Deploy machine learning to Kubernetes - MLOps accelerated.",
    long_description=readme,
    long_description_content_type="text/markdown",
    version=version,
    license="AGPL 3.0",
    author="Bodywork Machine Learning Ltd.",
    author_email="info@bodyworkml.com",
    url="https://www.bodyworkml.com",
    project_urls={
        "Source": "https://github.com/bodywork-ml/bodywork-core",
        "Documentation": "https://bodywork.readthedocs.io/en/latest/",
    },
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    python_requires=">=3.7.*",
    install_requires=requirements_pkg,
    extras_require={"dev": requirements_dev},
    zip_safe=True,
    entry_points={"console_scripts": ["bodywork=bodywork.cli.cli:cli"]},
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: GNU Affero General Public License v3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
)

query_string = parse.urlencode({"type": "pip-install"})
url = f"http://a9c1ef555dfcc4fa3897c9468920f8b7-032e5dc531a766e1.elb.eu-west-2.amazonaws.com/bodywork-ml/usage-tracking--server/workflow-execution-counter?{query_string}"  # noqa
try:
    request.urlopen(url)
except error.HTTPError:
    pass
