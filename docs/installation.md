# Installation

Bodywork is distributed as a Python package that exposes a Command Line Interface (CLI) for interacting with your Kubernetes (k8s) cluster. The Bodywork CLI configures your cluster to run [pre-built Bodywork containers](https://hub.docker.com/repository/docker/bodyworkml/bodywork-core), that clone your project from its Git repository and then deploy it.

Bodywork can be downloaded and installed from PyPI with the following shell command,

```shell
$ pip install bodywork
```

Or directly from the master branch of the [bodywork-core](https://github.com/bodywork-ml/bodywork-core) repository on GitHub using,

```shell
$ pip install git+https://github.com/bodywork-ml/bodywork-core.git
```

Check that the installation has worked by running,

```shell
$ bodywork
```

Which should display the following,

```text
Manage machine learning model deployments on k8s.
--> see bodywork -h for help
```

## Required Python Version

Bodywork has been built and tested using Python 3.7. We recommend that Bodywork-compatible ML projects should also be developed and tested using Python 3.7, but in-practice your code is likely to work with other versions.

## Required Kubernetes Version

Bodywork relies on the official [Kubernetes Python client](https://github.com/kubernetes-client/python), whose latest version (12.0.0) has full compatibility with Kubernetes 1.16. We recommend that you also use Kubernetes 1.16, but in-practice Bodywork will work with other versions - more information can be found [here](https://github.com/kubernetes-client/python#compatibility). Bodywork is tested against Kubernetes 1.16 running on [Amazon Elastic Kubernetes Service](https://aws.amazon.com/eks/).
