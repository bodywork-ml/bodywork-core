![bodywork](https://bodywork-media.s3.eu-west-2.amazonaws.com/website_logo_transparent_background.png)

---

[![Downloads](https://pepy.tech/badge/bodywork)](https://pepy.tech/project/bodywork)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/bodywork)](https://pypi.org/project/bodywork/)
[![PyPI - Bodywork Version](https://img.shields.io/pypi/v/bodywork.svg?label=PyPI&logo=PyPI&logoColor=white&color=success)](https://pypi.org/project/bodywork/)
![GitHub](https://img.shields.io/github/license/bodywork-ml/bodywork-core?color=success)

Bodywork is a deployment automation framework for machine learning in Python. It helps you schedule batch jobs, serve models and deploy ML pipelines, in containers on [Kubernetes](https://en.wikipedia.org/wiki/Kubernetes).

It automates repetitive and time-consuming tasks that machine learning engineers think of as [DevOps](https://en.wikipedia.org/wiki/DevOps), freeing them to focus on what they do best - solving data problems with machine learning.

![bodywork_diagram](https://bodywork-media.s3.eu-west-2.amazonaws.com/ml_pipeline.png)

Bodywork helps machine learning engineers to:

- **continuously deliver** - code for preparing features, training models, scoring data and defining model-scoring services. Bodywork containers running on Kubernetes will pull code directly from your project's Git repository, removing the need to build-and-push your own container images.
- **continuously deploy** - batch jobs, model-scoring services and complex ML pipelines, using the Bodywork workflow-controller to orchestrate end-to-end machine learning workflows on Kubernetes.

Bodywork handles automatic retires for batch jobs and for service deployments it will manage roll-backs and horizontal-scaling (via replication). It makes the deployment of highly-available and resilient machine learning systems, easy.

Bodywork uses Kubernetes for running machine learning jobs and services, because we believe that Kubernetes comes shipped with all the resources required for building an effective Machine Learning Operations ([MLOps](https://en.wikipedia.org/wiki/MLOps)) platform.

Bodywork is built and maintained by machine learning engineers, for machine learning engineers, and will always remain 100% open-source.

## Prerequisites

Before you start exploring what Bodywork can do for you, you will need:

- access to a Kubernetes cluster - either locally using [minikube](https://minikube.sigs.k8s.io/docs/) or [Docker-for-desktop](https://www.docker.com/products/docker-desktop), or as a managed service from a cloud provider, such as [EKS on AWS](https://aws.amazon.com/eks) or [AKS on Azure](https://azure.microsoft.com/en-us/services/kubernetes-service/).
- a [GitHub](https://github.com) account.

Familiarity with basic [Kubernetes concepts](https://kubernetes.io/docs/concepts/) and some exposure to the [kubectl](https://kubernetes.io/docs/reference/kubectl/overview/) command-line tool will make life easier. We recommend the first two introductory sections of Marko Lukša's excellent book [Kubernetes in Action](https://www.manning.com/books/kubernetes-in-action?query=kubernetes), or the introductory article we wrote on [Deploying Python ML Models with Flask, Docker and Kubernetes](https://alexioannides.com/2019/01/10/deploying-python-ml-models-with-flask-docker-and-kubernetes/).

## Documentation

The official documentation for bodywork-core can be found [here](https://bodywork.readthedocs.io/en/latest/). This is the best place to start.

## Contacting Us

If you:

- have a question that these pages haven't answered, then please ask a question on our [forum](https://bodywork.flarum.cloud).
- have found a bug, then please [open an issue]( https://github.com/bodywork-ml/bodywork-core/issues).
- would like to read the Bodywork source code, then you can find it [here](https://github.com/bodywork-ml/bodywork-core).
- would like to contribute, then please talk to us **first** at [info@bodyworkml.com](mailto:info@bodyworkml.com)
- would like to commission new functionality, then please contact us at [info@bodyworkml.com](mailto:info@bodyworkml.com)
