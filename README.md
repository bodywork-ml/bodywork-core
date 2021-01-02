![bodywork](https://bodywork-media.s3.eu-west-2.amazonaws.com/website_logo_transparent_background.png)

---

Bodywork is a Python framework that helps machine learning engineers run batch jobs, serve models and deploy machine learning pipelines, in containers on [Kubernetes](https://en.wikipedia.org/wiki/Kubernetes).

It automates repetitive and time-consuming tasks that machine learning engineers think of as [DevOps](https://en.wikipedia.org/wiki/DevOps), letting them focus on what they do best - solving data problems with machine learning.

## What Problems Does Bodywork Solve?

Running machine learning code in containers has become a common pattern to guarantee reproducibility between what has been developed and what is deployed in production environments.

Most machine learning engineers do not, however, have the time to develop the skills and expertise required to deliver and deploy containerised machine learning systems into production environments. This requires an understanding of how to build container images, how to push build artefacts to image repositories and how to configure a container orchestration platform to use these to execute batch jobs and deploy services.

Developing and maintaining these deployment pipelines is time-consuming. If there are multiple projects, each requiring re-training and re-deployment, then the management of these pipelines will quickly become a large burden.

This is where the Bodywork framework steps-in - to take responsibility for pulling you machine learning projects into containers and deploying them to the Kubernetes container orchestration platform. Bodywork can ensure that your projects are always trained with the latest data, the most recent models are always deployed and your machine learning systems remain generally available.

![bodywork_diagram](https://bodywork-media.s3.eu-west-2.amazonaws.com/ml_pipeline.png)

More specifically, Bodywork helps machine learning engineers to:

- **continuously deliver** - code for preparing features, training models, scoring data and defining model-scoring services. Bodywork containers running on Kubernetes will pull code directly from your project's Git repository, removing the need to build-and-push your own container images.
- **continuously deploy** - batch jobs, model-scoring services and complex machine learning pipelines, using the Bodywork workflow-controller to orchestrate end-to-end machine learning workflows on Kubernetes.

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
