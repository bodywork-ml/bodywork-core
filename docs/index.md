![bodywork](images/bodywork_logo.png)

Bodywork is a deployment framework for machine learning projects written in Python. It helps you to serve models, deploy ML pipelines and schedule batch jobs, in containers on [Kubernetes](https://en.wikipedia.org/wiki/Kubernetes).

It automates repetitive and time-consuming [DevOps](https://en.wikipedia.org/wiki/DevOps) tasks, freeing machine learning engineers to focus on what they do best - solving data problems with machine learning.

## Where does Bodywork Fit in your Stack?

Bodywork is aimed at teams who deploy (or intend to deploy) their machine learning projects in containers, to the cloud. Bodywork handles the delivery of your project's Python modules into containers and manages their deployment.

The process of building container images and deploying them to an orchestration platform is a complex engineering task. The diagram below shows the steps required to deploy a model-scoring service, together with the tools you could use to achieve this.

![old_devops_flow](images/ml_devops_flow.svg)

Developing and maintaining these deployment pipelines is time-consuming. If there are multiple projects, each requiring re-training and re-deployment, then without the type of automation that Bodywork provides, the management of these pipelines will quickly become a large burden.

## What does Bodywork Do?

Bodywork takes full responsibility for pulling you machine learning projects into containers and deploying them to a Kubernetes cluster. All of this is done directly from your Git repository - at no point is there any need to build Docker images and push them to a container registry. This process is shown below for a ML pipeline with two steps: train model (as a batch job) and then serve the trained model (as a REST API).

![bodywork_diagram](images/ml_pipeline.svg)

Bodywork can be configured to re-run this process on a schedule, so that the latest version of your codebase is always used when re-deploying the pipeline. This setup now forms an end-to-end CI/CD system for your machine learning project, as illustrated below.

![cicd](images/cicd_with_bodywork.svg)

Bodywork ensures that your projects are always trained with the latest data, the most recent models are always deployed and your machine learning systems remain highly-available.

## Key Features

* **continuously deploy** - batch jobs, model-scoring services as well as complex ML pipelines, using the Bodywork workflow-controller to orchestrate end-to-end machine learning workflows.
* **resilient deployments** - Bodywork handles automatic retires for batch jobs and for service deployments it will manage automatic roll-backs without any downtime.
* **horizontal scaling** - Bodywork can back your service endpoints with multiple container replicas to handle high volumes of traffic.
* **no new APIs to learn** - Bodywork does not require you to re-write your machine learning projects to conform to our view of how your codebase should be engineered. All you need to do is provide executable Python modules for starting services and running batch jobs.
* **no cloud platform lock-in** - Bodywork deploys to Kubernetes clusters, which are available as managed services from all major cloud providers. Kubernetes is indifferent to where it is running, so changing cloud provider is as easy as pointing to a different cluster.
* **written in Python** - the native language of machine learning and data science, so your team can have full visibility of what Bodywork is doing and how.
* **open-source** - Bodywork is built and maintained by machine learning engineers, for machine learning engineers, who are committed to keeping it 100% open-source.

Bodywork brings DevOps to your machine learning projects and will form the basis of your [Machine Learning Operations (MLOps)](https://en.wikipedia.org/wiki/MLOps) platform.

If this sounds good to you, then please give a ⭐️ to [Bodywork's GitHub repository](https://github.com/bodywork-ml/bodywork-core).

## Requirements

Before you start exploring what Bodywork can do for you, you will need:

* access to a Kubernetes cluster - either locally using [minikube](https://minikube.sigs.k8s.io/docs/) or [Docker-for-desktop](https://www.docker.com/products/docker-desktop), or as a managed service from a cloud provider, such as [EKS on AWS](https://aws.amazon.com/eks) or [AKS on Azure](https://azure.microsoft.com/en-us/services/kubernetes-service/).
* a [GitHub](https://github.com) account (we do not yet support GitLab or BitBucket).

Familiarity with basic [Kubernetes concepts](https://kubernetes.io/docs/concepts/) and some exposure to the [kubectl](https://kubernetes.io/docs/reference/kubectl/overview/) command-line tool will make life easier. We recommend the first two introductory sections of Marko Lukša's excellent book [Kubernetes in Action](https://www.manning.com/books/kubernetes-in-action?query=kubernetes), or the introductory article we wrote on [Deploying Python ML Models with Flask, Docker and Kubernetes](https://alexioannides.com/2019/01/10/deploying-python-ml-models-with-flask-docker-and-kubernetes/).

If you need help with any of this, then please don't hesitate to [contact us](contact.md) and we'll do our best to get you up-and-running.
