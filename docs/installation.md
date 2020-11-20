# Installation

Bodywork is a Python 3 package that exposes a Command Line Interface (CLI) for interacting with your Kubernetes (k8s) cluster to deploy Bodywork-compatible Machine Learning (ML) projects directly from Git repositories hosted on GitHub. It can be downloaded and installed from from PyPI with the following shell command,

```bash
pip install bodywork
```

Or directly from the master branch of the [bodywork-core](https://github.com/bodywork-ml/bodywork-core) repository on GitHub using,

```bash
pip install git+https://github.com/bodywork-ml/bodywork-core.git
```

Check that the installation has worked by running,

```bash
bodywork
```

Which should display the following,

```text
Manage machine learning model deployments on k8s.
--> see bodywork -h for help
```
