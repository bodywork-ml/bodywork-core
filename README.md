<div align="center">
<img src="https://bodywork-media.s3.eu-west-2.amazonaws.com/website_logo_transparent_background_full.png"/>
</div>

<div align="center">
<img src="https://pepy.tech/badge/bodywork"/>
<img src="https://img.shields.io/pypi/pyversions/bodywork"/>
<img src="https://img.shields.io/github/license/bodywork-ml/bodywork-core?color=success"/>
<img src="https://circleci.com/gh/bodywork-ml/bodywork-core.svg?style=shield"/>
<img src="https://codecov.io/gh/bodywork-ml/bodywork-core/branch/master/graph/badge.svg?token=QGPGZHVH9H"/>
<img src="https://img.shields.io/pypi/v/bodywork.svg?label=PyPI&logo=PyPI&logoColor=white&color=success"/>
</div>

---

Bodywork deploys machine learning projects developed in Python, to Kubernetes. It helps you to:

* serve models as microservices
* execute batch jobs
* run reproducible pipelines

On demand, or on a schedule. It automates repetitive DevOps tasks and frees machine learning engineers to focus on what they do best - solving data problems with machine learning.

## Get Started

Bodywork is distributed as a Python package - install it from [PyPI](https://pypi.org/project/bodywork/#description):

<div align="center">
<img src="https://bodywork-media.s3.eu-west-2.amazonaws.com/get_started_1.png"/>
</div>

Add a [bodywork.yaml](https://bodywork.readthedocs.io/en/latest/user_guide/#configuring-a-project-for-deployment-with-bodywork) file to your Python project’s Git repo. The contents of this file describe how your project will be deployed:

<div align="center">
<img src="https://bodywork-media.s3.eu-west-2.amazonaws.com/get_started_2.png"/>
</div>

Bodywork is used from the command-line to deploy projects to Kubernetes clusters. With a single command, you can start Bodywork containers (hosted by us on Docker Hub), that pull Python modules directly from your project’s Git repo, and run them:

<div align="center">
<img src="https://bodywork-media.s3.eu-west-2.amazonaws.com/get_started_3.png"/>
</div>

You don’t need to build Docker images or understand how to configure Kuberentes resources. Bodywork will fill the gap between executable Python modules and operational jobs and services on Kubernetes.

If you’re new to Kubernetes then check out our guide to [Kubernetes for ML](https://bodywork.readthedocs.io/en/latest/kubernetes/#getting-started-with-kubernetes) - we’ll have you up-and-running with a test cluster on your laptop, in under 10 minutes.

## Documentation

The documentation for bodywork-core can be found [here](https://bodywork.readthedocs.io/en/latest/). This is the best place to start.

## Deployment Templates

To accelerate your project's journey to production, we provide [deployment templates](https://bodywork.readthedocs.io/en/latest/template_projects/) for common use-cases:

* [batch scoring data](https://github.com/bodywork-ml/bodywork-batch-job-project)
* [deploying a model-scoring microservice with REST API](https://github.com/bodywork-ml/bodywork-serve-model-project)
* [scheduling a train-and-serve pipeline](https://github.com/bodywork-ml/bodywork-ml-pipeline-project)

## We want your Feedback

If Bodywork sounds like a useful tool, then please send us a signal with a GitHub ★

## Contacting Us

If you:

* Have a question that these pages haven't answered, or need help getting started with Kubernetes, then please use our [discussion board](https://github.com/bodywork-ml/bodywork-core/discussions).
* Have found a bug, then please [open an issue](https://github.com/bodywork-ml/bodywork-core/issues).
* Would like to contribute, then please talk to us **first** at [info@bodyworkml.com](mailto:info@bodyworkml.com).
* Would like to commission new functionality, then please contact us at [info@bodyworkml.com](mailto:info@bodyworkml.com).

Bodywork is brought to you by [Bodywork Machine Learning](https://www.bodyworkml.com).
