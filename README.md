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

Bodywork is a command line tool that deploys machine learning pipelines to [Kubernetes](https://en.wikipedia.org/wiki/Kubernetes). It takes care of everything to do with containers and orchestration, so that you don't have to.

## Who is this for?

Bodywork is aimed at teams who want a solution for running ML pipelines and deploying models to Kubernetes. It is a lightweight and simpler alternative to [Kubeflow](https://www.kubeflow.org), or to building your own platform based around a workflow orchestration tool like [Apache Airflow](https://airflow.apache.org), [Argo Workflows](https://argoproj.github.io/workflows/) or [Dagster](https://www.dagster.io).

## Pipeline = Jobs + Services

Any stage in a Bodywork pipeline can do one of two things:

- [x] **run a batch job**, to prepare features, train models, compute batch predictions, etc.
- [x] **start a long-running process**, like a Flask app that serves model predictions via HTTP.

You can use these to compose pipelines for many common ML use-cases, from serving pre-trained models to running continuous training on a schedule.

## No Boilerplate Code Required

Defining a stage is as simple as developing an executable Python module or Jupyter notebook that performs the required tasks, and then committing it to your project's Git repository. You are free to structure your codebase as you wish and there are no new APIs to learn.

<div align="center">
<img src="https://bodywork-media.s3.eu-west-2.amazonaws.com/project_structure_map.png"/ alt="Git project structure">
</div>

## Easy to Configure

Stages are assembled into [DAGs](https://en.wikipedia.org/wiki/Directed_acyclic_graph) that define your pipeline's workflow. This and other key [configuration](user_guide.md#configuring-a-project-for-deployment-with-bodywork) is contained within a single [bodywork.yaml file](https://github.com/bodywork-ml/bodywork-ml-pipeline-project/blob/master/bodywork.yaml).

## Simplified DevOps for ML

Bodywork removes the need for you to build and manage container images for any stage of your pipeline. It works by running all stages using Bodywork's [custom container image](https://hub.docker.com/repository/docker/bodyworkml/bodywork-core). Each stage starts by pulling all the required files directly from your project's Git repository (e.g., from GitHub), pip-installing any required dependencies, and then running the stage's designated Python module (or Jupyter notebook).

<div align="center">
<img src="https://bodywork-media.s3.eu-west-2.amazonaws.com/ml_pipeline.png"/>
</div>

## Get Started

Bodywork is distributed as a Python package - install it from [PyPI](https://pypi.org/project/bodywork/#description):

<div align="center">
<img src="https://bodywork-media.s3.eu-west-2.amazonaws.com/get_started_1_v2.png"/>
</div>

Add a [bodywork.yaml](https://bodywork.readthedocs.io/en/latest/user_guide/#configuring-a-project-for-deployment-with-bodywork) file to your Python project’s Git repo. The contents of this file describe how your project will be deployed:

<div align="center">
<img src="https://bodywork-media.s3.eu-west-2.amazonaws.com/get_started_2_v2.png"/>
</div>

Bodywork is used from the command-line to deploy projects to Kubernetes clusters. With a single command, you can start Bodywork containers (hosted by us on Docker Hub), that pull Python modules directly from your project’s Git repo, and run them:

<div align="center">
<img src="https://bodywork-media.s3.eu-west-2.amazonaws.com/get_started_3_v2.png"/>
</div>

You don’t need to build Docker images or understand how to configure Kuberentes resources. Bodywork will fill the gap between executable Python modules and operational jobs and services on Kubernetes.

If you’re new to Kubernetes then check out our guide to [Kubernetes for ML](https://bodywork.readthedocs.io/en/latest/kubernetes/#getting-started-with-kubernetes) - we’ll have you up-and-running with a test cluster on your laptop, in under 10 minutes.

## Documentation

The documentation for bodywork-core can be found [here](https://bodywork.readthedocs.io/en/latest/). This is the best place to start.

## Deployment Templates

To accelerate your project's journey to production, we provide [deployment templates](https://bodywork.readthedocs.io/en/latest/template_projects/) for common use-cases:

- [batch scoring data](https://github.com/bodywork-ml/bodywork-batch-job-project)
- [deploying a predict service with a REST API](https://github.com/bodywork-ml/bodywork-serve-model-project)
- [scheduling a continuous-training pipeline](https://github.com/bodywork-ml/bodywork-ml-pipeline-project)

## We want your Feedback

If Bodywork sounds like a useful tool, then please send us a signal with a GitHub ★

## Contacting Us

If you:

- Have a question that these pages haven't answered, or need help getting started with Kubernetes, then please use our [discussion board](https://github.com/bodywork-ml/bodywork-core/discussions).
- Have found a bug, then please [open an issue](https://github.com/bodywork-ml/bodywork-core/issues).
- Would like to contribute, then please talk to us **first** at [info@bodyworkml.com](mailto:info@bodyworkml.com).
- Would like to commission new functionality, then please contact us at [info@bodyworkml.com](mailto:info@bodyworkml.com).

Bodywork is brought to you by [Bodywork Machine Learning](https://www.bodyworkml.com).
