![bodywork](https://bodywork-media.s3.eu-west-2.amazonaws.com/website_logo_transparent_background.png)

---

Bodywork is a simple framework for machine learning engineers to run model-training workloads and deploy model-scoring services on [Kubernetes](https://en.wikipedia.org/wiki/Kubernetes). It is built by machine learning engineers, for machine learning engineers. It automates the repetitive tasks that most machine learning engineers think of as [DevOps](https://en.wikipedia.org/wiki/DevOps), allowing them to focus their time on what they do best - machine learning.

Bodywork uses Kubernetes for running machine learning workloads and services, because we believe that Kubernetes comes shipped with all the resources required for building an effective Machine Learning Operations ([MLOps](https://en.wikipedia.org/wiki/MLOps)) platform.

## What Problems Does Bodywork Solve?

Containerising machine learning code using Docker, pushing the build artefacts to an image repository and then configuring Kubernetes to orchestrate these into batch jobs and services, requires skills and expertise that most machine learning engineers do not have the time (and often the desire) to learn.

This is where Bodywork steps-in - to make sure that your code is delivered to the right place, at the right time, so that your models are trained, deployed and available to the rest of your team. Bodywork will:

- automate the configuration of Kubernetes jobs and deployments to run complex machine learning workflows that result in machine learning service deployments.
- continuously deliver machine learning code - for training models and defining model-scoring services - directly from your Git repository into running containers on Kubernetes.

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
